from __future__ import annotations

from datetime import datetime, timedelta, timezone
import io
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import require_admin, require_role
from app.db.session import get_session
from app.models.chat_log import ChatLog
from app.models.report_setting import ReportSetting
from app.models.ticket import Ticket
from app.models.user import User, UserRole
from app.schemas.report_settings import ReportSettingInput
from app.services.email_service import generate_analytics_pdf, send_analytics_report_email

router = APIRouter()


@router.get("/summary", response_model=Dict[str, Any])
def get_dashboard_summary(
    period: str = Query(
        "30d", description="Filter periode: 7d, 1w, 1m, 30d, 3m"
    ),
    db: Session = Depends(get_session),
    current_user: Optional[User] = None,
):
    """Mengambil data ringkasan untuk dashboard Admin.

    Catatan: endpoint ini juga dipakai scheduler background.
    Jadi `current_user` dibuat optional.
    """

    logger.info(
        "Dashboard Analytics diakses. user=%s period=%s",
        getattr(current_user, "email", None) or "Scheduler",
        period,
    )

    try:
        now = datetime.now(timezone.utc)

        if period in ("7d", "1w"):

            days = 7
        elif period == "1m":
            days = 30
        elif period == "3m":
            days = 90
        else:
            days = 30

        start_current = now - timedelta(days=days)
        start_previous = start_current - timedelta(days=days)

        def to_utc(dt: datetime) -> datetime:
            if dt is None:
                return None
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)

        def get_trend_details(current: float, previous: float) -> Dict[str, Any]:
            if previous == 0:
                trend_value = 100.0 if current > 0 else 0.0
            else:
                trend_value = round(((current - previous) / previous) * 100, 1)

            if trend_value > 0:
                text = f"Meningkat {trend_value}% dibanding periode sebelumnya"
                direction = "up"
            elif trend_value < 0:
                text = f"Menurun {abs(trend_value)}% dibanding periode sebelumnya"
                direction = "down"
            else:
                text = "Stabil dibanding periode sebelumnya"
                direction = "flat"

            return {"value": trend_value, "text": text, "direction": direction}

        # Convert to naive UTC for database comparison (matches stored DB timestamps)
        start_current_naive = start_current.replace(tzinfo=None)
        start_previous_naive = start_previous.replace(tzinfo=None)

        total_tickets_current = db.query(Ticket).filter(Ticket.created_at >= start_current_naive).count()
        prev_tickets_count = (
            db.query(Ticket)
            .filter(Ticket.created_at >= start_previous_naive, Ticket.created_at < start_current_naive)
            .count()
        )
        ticket_trend = get_trend_details(total_tickets_current, prev_tickets_count)

        resolved_tickets = db.query(Ticket).filter(
            Ticket.created_at >= start_current_naive,
            Ticket.status.in_(["closed", "answered"]),
        ).all()

        resolved_count = len(resolved_tickets)
        resolution_rate = (
            round((resolved_count / total_tickets_current * 100), 1)
            if total_tickets_current > 0
            else 0
        )

        prev_resolved_tickets = db.query(Ticket).filter(
            Ticket.created_at >= start_previous_naive,
            Ticket.created_at < start_current_naive,
            Ticket.status.in_(["closed", "answered"]),
        ).all()

        prev_resolved_count = len(prev_resolved_tickets)
        prev_resolution_rate = (
            round((prev_resolved_count / prev_tickets_count * 100), 1)
            if prev_tickets_count > 0
            else 0
        )
        ticket_resolution_trend = get_trend_details(resolution_rate, prev_resolution_rate)

        total_seconds = sum(
            (to_utc(t.updated_at) - to_utc(t.created_at)).total_seconds()
            for t in resolved_tickets
            if t.updated_at and t.created_at
        )
        avg_resolution_seconds = total_seconds / resolved_count if resolved_count > 0 else 0

        def format_duration(seconds: float) -> str:
            days = int(seconds // 86400)
            seconds = int(seconds % 86400)
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            seconds = seconds % 60
            return f"{days:02d}:{hours:02d}:{minutes:02d}:{seconds:02d}"

        avg_resolution_time = format_duration(avg_resolution_seconds)

        prev_total_seconds = sum(
            (to_utc(t.updated_at) - to_utc(t.created_at)).total_seconds()
            for t in prev_resolved_tickets
            if t.updated_at and t.created_at
        )
        prev_avg_resolution_seconds = (
            prev_total_seconds / prev_resolved_count if prev_resolved_count > 0 else 0
        )
        avg_time_trend = get_trend_details(avg_resolution_seconds, prev_avg_resolution_seconds)

        current_chats = db.query(ChatLog).filter(ChatLog.created_at >= start_current_naive).count()
        prev_chats = db.query(ChatLog).filter(
            ChatLog.created_at >= start_previous_naive,
            ChatLog.created_at < start_current_naive,
        ).count()
        chat_trend = get_trend_details(current_chats, prev_chats)

        resolved_chats = db.query(ChatLog).filter(
            ChatLog.created_at >= start_current_naive,
            ChatLog.is_resolved == True,
        ).count()
        chat_resolution_rate = (
            round((resolved_chats / current_chats * 100), 1) if current_chats > 0 else 0
        )

        prev_resolved_chats = db.query(ChatLog).filter(
            ChatLog.created_at >= start_previous_naive,
            ChatLog.created_at < start_current_naive,
            ChatLog.is_resolved == True,
        ).count()
        prev_chat_resolution_rate = (
            round((prev_resolved_chats / prev_chats * 100), 1) if prev_chats > 0 else 0
        )
        chat_resolution_trend = get_trend_details(chat_resolution_rate, prev_chat_resolution_rate)

        daily_stats_query = (
            db.query(
                func.date(Ticket.created_at).label("date"),
                func.count(Ticket.id).label("count"),
            )
            .filter(Ticket.created_at >= start_current_naive)
            .group_by(func.date(Ticket.created_at))
            .order_by(func.date(Ticket.created_at))
            .all()
        )
        chart_data = [{"date": str(stat.date), "count": stat.count} for stat in daily_stats_query]

        category_counts = (
            db.query(Ticket.category, func.count(Ticket.id).label("count"))
            .filter(Ticket.created_at >= start_current_naive)
            .group_by(Ticket.category)
            .order_by(func.count(Ticket.id).desc())
            .all()
        )

        problem_frequency = []
        for cat, count in category_counts:
            if cat:
                cat_lower = cat.lower()
                keyword_count = db.query(ChatLog).filter(
                    ChatLog.created_at >= start_current_naive,
                    ChatLog.user_query.ilike(f"%{cat_lower}%"),
                ).count()
            else:
                keyword_count = 0

            problem_frequency.append(
                {
                    "category": cat,
                    "ticket_count": count,
                    "chat_count": keyword_count,
                    "escalation_rate": f"{round((count / keyword_count * 100), 1)}%"
                    if keyword_count > 0
                    else "0%",
                }
            )

        return {
            "period": period,
            "chatbot_metrics": {
                "total_interactions": current_chats,
                "interactions_trend": chat_trend,
                "resolution_rate": chat_resolution_rate,
                "resolution_trend": chat_resolution_trend,
            },
            "ticket_metrics": {
                "total_escalations": total_tickets_current,
                "escalations_trend": ticket_trend,
                "resolution_rate": resolution_rate,
                "resolution_trend": ticket_resolution_trend,
                "avg_resolution_time": avg_resolution_time,
                "avg_resolution_time_trend": avg_time_trend,
            },
            "chart_data": chart_data,
            "problem_frequency": problem_frequency,
        }

    except Exception as e:
        logger.error(f"Gagal mengambil data analytics: {str(e)}")
        raise HTTPException(status_code=500, detail="Terjadi kesalahan saat menghitung data analytics")


@router.get("/export-pdf")
def export_analytics_to_pdf(
    period: str = Query("30d", description="Filter periode: 7d, 1w, 1m, 30d, 3m"),
    db: Session = Depends(get_session),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Administrator mendownload report dalam format PDF."""

    try:
        now = datetime.now(timezone.utc)

        if period in ("7d", "1w"):
            days = 7
        elif period == "1m":
            days = 30
        elif period == "3m":
            days = 90
        else:
            days = 30

        start_date = now - timedelta(days=days)
        # Convert to naive for DB comparison
        start_date_naive = start_date.replace(tzinfo=None)

        start_str = start_date.strftime("%d%m%Y")
        end_str = now.strftime("%d%m%Y")
        filename = f"Laporan_{start_str}-{end_str}.pdf"

        tickets = db.query(Ticket).filter(Ticket.created_at >= start_date_naive).all()
        dashboard_summary = get_dashboard_summary(period=period, db=db)

        report_data = {
            "period": period,
            "generated_at": now.strftime("%d/%m/%Y %H:%M"),
            "start_date": start_date.strftime("%d/%m/%Y"),
            "end_date": now.strftime("%d/%m/%Y"),
            "tickets": tickets,
            "ticket_metrics": dashboard_summary.get("ticket_metrics", {}),
            "chatbot_metrics": dashboard_summary.get("chatbot_metrics", {}),
            "problem_frequency": dashboard_summary.get("problem_frequency", []),
        }

        pdf_bytes = generate_analytics_pdf(report_data)

        output = io.BytesIO(pdf_bytes)
        headers = {"Content-Disposition": f"attachment; filename=\"{filename}\""}
        return StreamingResponse(output, headers=headers, media_type="application/pdf")

    except Exception as e:
        logger.error(f"Gagal generate PDF: {e}")
        raise HTTPException(status_code=500, detail="Gagal mengunduh laporan PDF")


@router.post("/report-settings")
def save_report_settings(
    setting_in: ReportSettingInput,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """Menyimpan konfigurasi pengiriman laporan otomatis (scheduler)."""

    valid_periods = ["1w", "1m", "3m"]
    if setting_in.period not in valid_periods:
        raise HTTPException(
            status_code=400,
            detail="Periode tidak valid. Gunakan: 1w, 1m, 3m",
        )

    existing_setting = (
        db.query(ReportSetting)
        .filter(ReportSetting.recipient_email == setting_in.recipient_email)
        .first()
    )

    if existing_setting:
        existing_setting.period = setting_in.period
        existing_setting.is_active = True
        message = "Konfigurasi laporan berhasil diperbarui."
    else:
        new_setting = ReportSetting(
            recipient_email=setting_in.recipient_email,
            period=setting_in.period,
        )
        db.add(new_setting)
        message = "Konfigurasi laporan berhasil disimpan."

    db.commit()
    logger.info(
        f"Admin {current_user.email} menyimpan konfigurasi report untuk {setting_in.recipient_email}"
    )
    return {"message": message}


@router.get("/report-settings")
def get_report_settings(
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """Mengambil list konfigurasi untuk ditampilkan di UI."""

    rows = db.query(ReportSetting).all()
    return rows

