from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from loguru import logger
from typing import Dict, Any
from datetime import datetime, timedelta
from app.core.config import settings
from app.services.email_service import send_email_via_brevo, send_analytics_report_email
from fastapi.responses import StreamingResponse
import pandas as pd
import io

from app.models.user import User, UserRole
from app.core.dependencies import require_admin, require_role
from app.db.session import get_session
from app.models.ticket import Ticket
from app.models.chat_log import ChatLog 

router = APIRouter()

@router.get("/summary", response_model=Dict[str, Any])
def get_dashboard_summary(
    period: str = Query("30d", description="Filter periode: 7d, 30d, 3m"),
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin)
):
    """
    Mengambil data ringkasan untuk dashboard Admin secara lengkap sesuai desain UI baru.
    Mendukung filter waktu, perbandingan tren (%), dan rata-rata waktu penyelesaian.
    """
    logger.info(f"Admin {current_user.email} mengakses Analytics Dashboard (Periode: {period}).")
    
    try:
        now = datetime.utcnow()
        
        if period == "7d":
            days = 7
        elif period == "3m":
            days = 90
        else:
            days = 30
            
        start_current = now - timedelta(days=days)
        start_previous = start_current - timedelta(days=days)

        def calculate_trend(current, previous):
            if previous == 0:
                return 100.0 if current > 0 else 0.0
            return round(((current - previous) / previous) * 100, 1)

        current_tickets = db.query(Ticket).filter(Ticket.created_at >= start_current).all()
        prev_tickets_count = db.query(Ticket).filter(Ticket.created_at >= start_previous, Ticket.created_at < start_current).count()
        
        total_tickets_current = len(current_tickets)
        ticket_trend = calculate_trend(total_tickets_current, prev_tickets_count)

        resolved_tickets = [t for t in current_tickets if t.status in ["closed", "answered"]]
        resolved_count = len(resolved_tickets)
        resolution_rate = round((resolved_count / total_tickets_current * 100), 1) if total_tickets_current > 0 else 0

        prev_resolved_count = db.query(Ticket).filter(
            Ticket.created_at >= start_previous, 
            Ticket.created_at < start_current,
            Ticket.status.in_(["closed", "answered"])
        ).count()
        prev_resolution_rate = round((prev_resolved_count / prev_tickets_count * 100), 1) if prev_tickets_count > 0 else 0
        ticket_resolution_trend = calculate_trend(resolution_rate, prev_resolution_rate)

        total_seconds = 0
        for t in resolved_tickets:
            if t.updated_at and t.created_at:
                total_seconds += (t.updated_at - t.created_at).total_seconds()
        
        avg_resolution_seconds = total_seconds / resolved_count if resolved_count > 0 else 0
        avg_resolution_time = str(timedelta(seconds=int(avg_resolution_seconds))) # Format HH:MM:SS

        current_chats = db.query(ChatLog).filter(ChatLog.created_at >= start_current).count()
        prev_chats = db.query(ChatLog).filter(ChatLog.created_at >= start_previous, ChatLog.created_at < start_current).count()
        chat_trend = calculate_trend(current_chats, prev_chats)

        resolved_chats = db.query(ChatLog).filter(ChatLog.created_at >= start_current, ChatLog.is_resolved == True).count()
        chat_resolution_rate = round((resolved_chats / current_chats * 100), 1) if current_chats > 0 else 0

        prev_resolved_chats = db.query(ChatLog).filter(
            ChatLog.created_at >= start_previous, 
            ChatLog.created_at < start_current,
            ChatLog.is_resolved == True
        ).count()
        prev_chat_resolution_rate = round((prev_resolved_chats / prev_chats * 100), 1) if prev_chats > 0 else 0
        chat_resolution_trend = calculate_trend(chat_resolution_rate, prev_chat_resolution_rate)

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
            chat_count_estimation = count * 3 
            
            problem_frequency.append({
                "category": cat,
                "ticket_count": count,
                "chat_count": chat_count_estimation, 
                "escalation_rate": f"{round((count / chat_count_estimation * 100), 1)}%" if chat_count_estimation > 0 else "0%"
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
            },
            "chart_data": chart_data,
            "problem_frequency": problem_frequency
        }
        
    except Exception as e:
        logger.error(f"Gagal mengambil data analytics: {str(e)}")
        raise HTTPException(status_code=500, detail="Terjadi kesalahan saat menghitung data analytics")
    

@router.get("/export-excel")
def export_analytics_to_excel(
    db: Session = Depends(get_session),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.MANAGER))
):
    """
    Administrator & Manager mendownload report (Excel).
    """
    try:
        tickets = db.query(Ticket).all()
        
        data = []
        for t in tickets:
            data.append({
                "ID Tiket": t.id,
                "Email User": t.user_email,
                "Subjek": t.subject,
                "Kategori": t.category,
                "Divisi": t.division,
                "Status": t.status,
                "Tanggal Dibuat": t.created_at.strftime("%Y-%m-%d %H:%M")
            })
        
        df = pd.DataFrame(data)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Report Tiket')
        
        output.seek(0)

        headers = {
            'Content-Disposition': 'attachment; filename="report_analytics_epsolve.xlsx"'
        }
        return StreamingResponse(output, headers=headers, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    except Exception as e:
        logger.error(f"Gagal generate Excel: {e}")
        raise HTTPException(status_code=500, detail="Gagal mengunduh laporan Excel")


@router.post("/distribute-report")
def distribute_report_to_managers(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin)
):
    """
    Administrator mengirim email otomatis ke semua Manajer.
    """
    try:
        report_data = get_dashboard_summary(period="30d", db=db, current_user=current_user)
        
        managers = db.query(User).filter(User.role == UserRole.MANAGER).all()
        
        if not managers:
            managers = [current_user]

        for manager in managers:
            background_tasks.add_task(
                send_analytics_report_email,
                user_email=manager.email,
                user_name=manager.full_name,
                report_data=report_data
            )
        
        return {"message": f"Laporan berhasil dikirim ke {len(managers)} Manajer."}

    except Exception as e:
        logger.error(f"Gagal distribusi laporan: {e}")
        raise HTTPException(status_code=500, detail="Terjadi kesalahan saat mendistribusikan laporan")