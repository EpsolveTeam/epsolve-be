from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from loguru import logger
from typing import Dict, Any
from datetime import datetime, timedelta
from app.core.config import settings
from app.services.email_service import send_email_via_brevo, send_analytics_report_email, generate_analytics_pdf
from fastapi.responses import StreamingResponse
import io

from app.models.user import User, UserRole
from app.core.dependencies import require_admin, require_role
from app.db.session import get_session
from app.models.ticket import Ticket
from app.models.chat_log import ChatLog
from app.models.auto_report import AutoReportSetting

router = APIRouter()

VALID_PERIODS = {"off", "1w", "1m", "3m"}


@router.get("/auto-report-settings")
def get_auto_report_settings(
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin)
):
    setting = db.get(AutoReportSetting, 1)
    if not setting:
        return {"email": "", "period": "off", "is_active": False}
    return {"email": setting.email, "period": setting.period, "is_active": setting.is_active}


@router.put("/auto-report-settings")
def save_auto_report_settings(
    email: str = Query(""),
    period: str = Query("off"),
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin)
):
    if period not in VALID_PERIODS:
        raise HTTPException(status_code=400, detail="Periode tidak valid. Gunakan: off, 1w, 1m, 3m")

    setting = db.get(AutoReportSetting, 1)
    if not setting:
        setting = AutoReportSetting(id=1)
        db.add(setting)

    setting.email = email
    setting.period = period
    setting.is_active = period != "off"
    setting.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(setting)

    logger.info(f"Auto-report setting diperbarui oleh {current_user.email}: period={period}, email={email}")
    return {"message": "Pengaturan laporan otomatis berhasil disimpan.", "period": period, "is_active": setting.is_active}

@router.get("/summary", response_model=Dict[str, Any])
def get_dashboard_summary(
    period: str = Query("30d", description="Filter periode: 7d, 1w, 1m, 30d, 3m"),
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin)
):
    """
    Mengambil data ringkasan untuk dashboard Admin secara lengkap sesuai desain UI baru.
    Menghandle insight text (Meningkat/Menurun) langsung dari backend (BFF Pattern).
    """
    logger.info(f"Admin {current_user.email} mengakses Analytics Dashboard (Periode: {period}).")
    
    try:
        now = datetime.utcnow()
        
        if period == "7d":
            days = 7
        elif period == "1w":
            days = 7
        elif period == "1m":
            days = 30
        elif period == "3m":
            days = 90
        else:
            days = 30
            
        start_current = now - timedelta(days=days)
        start_previous = start_current - timedelta(days=days)

        def format_duration(seconds):
            seconds = int(seconds)
            days    = seconds // 86400
            hours   = (seconds % 86400) // 3600
            minutes = (seconds % 3600) // 60
            if days > 0:
                return f"{days}h {hours}j {minutes}m"
            elif hours > 0:
                return f"{hours}j {minutes}m"
            elif minutes > 0:
                return f"{minutes}m"
            else:
                return "< 1m"

        def get_trend_details(current, previous, invert=False):
            if previous == 0:
                return {
                    "value": 0.0,
                    "text": "Tidak ada data periode sebelumnya",
                    "direction": "flat"
                }

            trend_value = round(((current - previous) / previous) * 100, 1)

            if trend_value > 0:
                if invert:
                    text = f"Lebih lambat {trend_value}% dibanding periode sebelumnya"
                    direction = "down"
                else:
                    text = f"Meningkat {trend_value}% dibanding periode sebelumnya"
                    direction = "up"
            elif trend_value < 0:
                if invert:
                    text = f"Lebih cepat {abs(trend_value)}% dibanding periode sebelumnya"
                    direction = "up"
                else:
                    text = f"Menurun {abs(trend_value)}% dibanding periode sebelumnya"
                    direction = "down"
            else:
                text = "Stabil dibanding periode sebelumnya"
                direction = "flat"

            return {
                "value": abs(trend_value),
                "text": text,
                "direction": direction
            }

        total_tickets_current = db.query(Ticket).filter(Ticket.created_at >= start_current).count()
        prev_tickets_count = db.query(Ticket).filter(Ticket.created_at >= start_previous, Ticket.created_at < start_current).count()
        ticket_trend = get_trend_details(total_tickets_current, prev_tickets_count)
        
        resolved_tickets = db.query(Ticket).filter(
            Ticket.created_at >= start_current, 
            Ticket.status.in_(["closed", "answered"])
        ).all()
        resolved_count = len(resolved_tickets)
        resolution_rate = round((resolved_count / total_tickets_current * 100), 1) if total_tickets_current > 0 else 0

        prev_resolved_tickets = db.query(Ticket).filter(
            Ticket.created_at >= start_previous, 
            Ticket.created_at < start_current,
            Ticket.status.in_(["closed", "answered"])
        ).all()
        prev_resolved_count = len(prev_resolved_tickets)
        prev_resolution_rate = round((prev_resolved_count / prev_tickets_count * 100), 1) if prev_tickets_count > 0 else 0
        
        ticket_resolution_trend = get_trend_details(resolution_rate, prev_resolution_rate)

        total_seconds = 0
        count_with_time = 0
        for t in resolved_tickets:
            upd = getattr(t, "updated_at", None)
            cre = getattr(t, "created_at", None)
            if upd and cre:
                try:
                    total_seconds += (upd.replace(tzinfo=None) - cre.replace(tzinfo=None)).total_seconds()
                    count_with_time += 1
                except Exception:
                    pass
        avg_resolution_seconds = total_seconds / count_with_time if count_with_time > 0 else 0
        avg_resolution_time = format_duration(avg_resolution_seconds)

        prev_total_seconds = 0
        prev_count_with_time = 0
        for t in prev_resolved_tickets:
            upd = getattr(t, "updated_at", None)
            cre = getattr(t, "created_at", None)
            if upd and cre:
                try:
                    prev_total_seconds += (upd.replace(tzinfo=None) - cre.replace(tzinfo=None)).total_seconds()
                    prev_count_with_time += 1
                except Exception:
                    pass
        prev_avg_resolution_seconds = prev_total_seconds / prev_count_with_time if prev_count_with_time > 0 else 0
        avg_time_trend = get_trend_details(avg_resolution_seconds, prev_avg_resolution_seconds, invert=True)

        current_questions = db.query(ChatLog).filter(ChatLog.created_at >= start_current).count()
        prev_questions = db.query(ChatLog).filter(ChatLog.created_at >= start_previous, ChatLog.created_at < start_current).count()
        questions_trend = get_trend_details(current_questions, prev_questions)

        current_interactions = db.query(func.count(func.distinct(ChatLog.session_id))).filter(ChatLog.created_at >= start_current).scalar() or 0
        prev_interactions = db.query(func.count(func.distinct(ChatLog.session_id))).filter(ChatLog.created_at >= start_previous, ChatLog.created_at < start_current).scalar() or 0
        interactions_trend = get_trend_details(current_interactions, prev_interactions)

        resolved_chats = db.query(ChatLog).filter(ChatLog.created_at >= start_current, ChatLog.is_resolved == True).count()
        chat_resolution_rate = round((resolved_chats / current_questions * 100), 1) if current_questions > 0 else 0

        prev_resolved_chats = db.query(ChatLog).filter(ChatLog.created_at >= start_previous, ChatLog.created_at < start_current, ChatLog.is_resolved == True).count()
        prev_chat_resolution_rate = round((prev_resolved_chats / prev_questions * 100), 1) if prev_questions > 0 else 0
        chat_resolution_trend = get_trend_details(chat_resolution_rate, prev_chat_resolution_rate)

        daily_stats_query = (
            db.query(
                func.date(Ticket.created_at).label('date'),
                func.count(Ticket.id).label('count')
            )
            .filter(Ticket.created_at >= start_current)
            .group_by(func.date(Ticket.created_at))
            .order_by(func.date(Ticket.created_at))
            .all()
        )
        chart_data = [{"date": str(stat.date), "count": stat.count} for stat in daily_stats_query]

        category_counts = db.query(
            Ticket.category, 
            func.count(Ticket.id).label("count")
        ).filter(Ticket.created_at >= start_current).group_by(Ticket.category).order_by(func.count(Ticket.id).desc()).all()

        problem_frequency = []
        for cat, count in category_counts:
            if cat:
                user_ids = [
                    r.user_id for r in db.query(Ticket.user_id).filter(
                        Ticket.created_at >= start_current,
                        Ticket.category == cat,
                        Ticket.user_id.isnot(None)
                    ).all()
                ]
                chat_count = db.query(ChatLog).filter(
                    ChatLog.created_at >= start_current,
                    ChatLog.user_id.in_(user_ids)
                ).count() if user_ids else 0
            else:
                chat_count = 0

            problem_frequency.append({
                "category": cat,
                "ticket_count": count,
                "chat_count": chat_count,
                "escalation_rate": f"{round((count / chat_count * 100), 1)}%" if chat_count > 0 else "0%"
            })

        return {
            "period": period,
            "chatbot_metrics": {
                "total_questions": current_questions,
                "questions_trend": questions_trend,
                "total_interactions": current_interactions,
                "interactions_trend": interactions_trend,
                "resolution_rate": chat_resolution_rate,
                "resolution_trend": chat_resolution_trend
            },
            "ticket_metrics": {
                "total_escalations": total_tickets_current,
                "escalations_trend": ticket_trend,
                "resolution_rate": resolution_rate,
                "resolution_trend": ticket_resolution_trend,
                "avg_resolution_time": avg_resolution_time,
                "avg_resolution_time_trend": avg_time_trend
            },
            "chart_data": chart_data,
            "problem_frequency": problem_frequency
        }
        
    except Exception as e:
        logger.error(f"Gagal mengambil data analytics: {str(e)}")
        raise HTTPException(status_code=500, detail="Terjadi kesalahan saat menghitung data analytics")

@router.get("/export-pdf")
def export_analytics_to_pdf(
    period: str = Query("30d", description="Filter periode: 7d, 1w, 1m, 30d, 3m"),
    db: Session = Depends(get_session),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """
    Administrator mendownload report dalam format PDF.
    Nama file: Laporan_DDMMYYYY-DDMMYYYY.pdf
    """
    try:
        now = datetime.utcnow()
        
        if period == "7d" or period == "1w":
            days = 7
        elif period == "1m":
            days = 30
        elif period == "3m":
            days = 90
        else:
            days = 30
            
        start_date = now - timedelta(days=days)
        
        start_str = start_date.strftime("%d%m%Y")
        end_str = now.strftime("%d%m%Y")
        filename = f"Laporan_{start_str}-{end_str}.pdf"
        
        tickets = db.query(Ticket).filter(Ticket.created_at >= start_date).all()
        
        report_data = {
            "period": period,
            "generated_at": now.strftime("%d/%m/%Y %H:%M"),
            "start_date": start_date.strftime("%d/%m/%Y"),
            "end_date": now.strftime("%d/%m/%Y"),
            "tickets": tickets
        }
        
        pdf_bytes = generate_analytics_pdf(report_data)
        
        output = io.BytesIO(pdf_bytes)
        
        headers = {
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
        return StreamingResponse(output, headers=headers, media_type='application/pdf')

    except Exception as e:
        logger.error(f"Gagal generate PDF: {e}")
        raise HTTPException(status_code=500, detail="Gagal mengunduh laporan PDF")


@router.post("/distribute-report")
def distribute_report(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin)
):
    """
    Mengirim laporan otomatis ke email seluruh admin (periode default: 3m).
    """
    try:
        period = "3m"
        report_data = get_dashboard_summary(period=period, db=db, current_user=current_user)
        
        admins = db.query(User).filter(User.role == UserRole.ADMIN).all()
        for admin in admins:
            background_tasks.add_task(
                send_analytics_report_email,
                user_email=admin.email,
                user_name=admin.full_name,
                report_data=report_data
            )
        
        return {"message": "Laporan sedang dikirim ke seluruh admin."}

    except Exception as e:
        logger.error(f"Gagal distribusi laporan: {e}")
        raise HTTPException(status_code=500, detail="Terjadi kesalahan saat mendistribusikan laporan")