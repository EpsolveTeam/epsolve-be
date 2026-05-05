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

router = APIRouter()

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

        def get_trend_details(current, previous):
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

            return {
                "value": trend_value,  
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
        avg_resolution_time = str(timedelta(seconds=int(avg_resolution_seconds)))

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
        avg_time_trend = get_trend_details(avg_resolution_seconds, prev_avg_resolution_seconds)

        current_chats = db.query(ChatLog).filter(ChatLog.created_at >= start_current).count()
        prev_chats = db.query(ChatLog).filter(ChatLog.created_at >= start_previous, ChatLog.created_at < start_current).count()
        chat_trend = get_trend_details(current_chats, prev_chats)

        resolved_chats = db.query(ChatLog).filter(ChatLog.created_at >= start_current, ChatLog.is_resolved == True).count()
        chat_resolution_rate = round((resolved_chats / current_chats * 100), 1) if current_chats > 0 else 0

        prev_resolved_chats = db.query(ChatLog).filter(ChatLog.created_at >= start_previous, ChatLog.created_at < start_current, ChatLog.is_resolved == True).count()
        prev_chat_resolution_rate = round((prev_resolved_chats / prev_chats * 100), 1) if prev_chats > 0 else 0
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
                cat_lower = cat.lower()
                keyword_count = db.query(ChatLog).filter(
                    ChatLog.created_at >= start_current,
                    ChatLog.user_query.ilike(f"%{cat_lower}%")
                ).count()
            else:
                keyword_count = 0
            
            problem_frequency.append({
                "category": cat,
                "ticket_count": count,
                "chat_count": keyword_count, 
                "escalation_rate": f"{round((count / keyword_count * 100), 1)}%" if keyword_count > 0 else "0%"
            })

        return {
            "period": period,
            "chatbot_metrics": {
                "total_interactions": current_chats,
                "interactions_trend": chat_trend,
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