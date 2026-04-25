from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from loguru import logger
from typing import Dict, Any
from datetime import datetime, timedelta
from app.core.config import settings

from app.models.user import User
from app.core.dependencies import require_admin
from app.db.session import get_session
from app.models.ticket import Ticket
from app.models.chat_log import ChatLog 
import resend

router = APIRouter()

resend.api_key = settings.RESEND_API_KEY

@router.get("/summary", response_model=Dict[str, Any])
def get_dashboard_summary(
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin)
):
    """
    Mengambil data ringkasan untuk dashboard Admin secara lengkap.
    Termasuk metrik tiket, chart per hari, frekuensi masalah, dan metrik chat.
    """
    logger.info(f"Admin dengan ID {current_user.id} sedang mengakses data Analytics Dashboard.")
    
    try:
        total_tickets = db.query(Ticket).count()
        open_tickets = db.query(Ticket).filter(Ticket.status == "open").count()
        closed_tickets = db.query(Ticket).filter(Ticket.status.in_(["answered", "closed"])).count()
        
        today = datetime.utcnow().date()
        seven_days_ago = today - timedelta(days=7)
        
        daily_stats_query = (
            db.query(
                func.date(Ticket.created_at).label('date'),
                func.count(Ticket.id).label('count')
            )
            .filter(Ticket.created_at >= seven_days_ago)
            .group_by(func.date(Ticket.created_at))
            .order_by(func.date(Ticket.created_at))
            .all()
        )
        chart_data = [{"date": str(stat.date), "count": stat.count} for stat in daily_stats_query]

        category_counts = db.query(
            Ticket.category, 
            func.count(Ticket.id).label("count")
        ).group_by(Ticket.category).order_by(func.count(Ticket.id).desc()).all()

        problem_frequency = [
            {"category": cat, "count": count} for cat, count in category_counts
        ]

        total_chats = db.query(func.count(ChatLog.id)).scalar() or 0
        resolved_by_bot = db.query(func.count(ChatLog.id)).filter(ChatLog.is_resolved == True).scalar() or 0

        return {
            "ticket_metrics": {
                "total": total_tickets,
                "open": open_tickets,
                "closed": closed_tickets
            },
            "chart_data": chart_data,
            "problem_frequency": problem_frequency,
            "chatbot_metrics": {
                "total_interactions": total_chats,
                "resolved_by_bot": resolved_by_bot
            }
        }
        
    except Exception as e:
        logger.error(f"Gagal mengambil data analytics: {str(e)}")
        raise HTTPException(status_code=500, detail="Terjadi kesalahan saat menghitung data analytics")
    
@router.post("/send-report")
def send_analytics_report_via_email(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin)
):
    """
    Endpoint untuk mengirim laporan Analytics via Email ke Admin/Manajer yang me-request.
    """
    try:
        # Ambil data dari fungsi summary
        report_data = get_dashboard_summary(db=db, current_user=current_user)
        
        total_tickets = report_data["ticket_metrics"]["total"]
        open_tickets = report_data["ticket_metrics"]["open"]
        total_chats = report_data["chatbot_metrics"]["total_interactions"]
        
        email_html = f"""
        <div style="font-family: sans-serif; color: #333;">
            <h2>📊 Laporan Mingguan Epsolve Helpdesk</h2>
            <p>Halo {current_user.full_name}, berikut adalah ringkasan kinerja Helpdesk saat ini:</p>
            <ul>
                <li><strong>Total Tiket Masuk:</strong> {total_tickets} tiket</li>
                <li><strong>Tiket Belum Selesai (Open):</strong> {open_tickets} tiket</li>
                <li><strong>Total Interaksi Chatbot:</strong> {total_chats} percakapan</li>
            </ul>
            <p>Silakan login ke Dashboard untuk melihat data grafik secara detail.</p>
        </div>
        """

        def send_email_task():
            resend.Emails.send({
                "from": "Epsolve Report <onboarding@resend.dev>",
                "to": current_user.email,
                "subject": "📊 Ringkasan Laporan Helpdesk Epsolve",
                "html": email_html
            })

        # Jalankan di background agar API response tidak lemot menunggu email terkirim
        background_tasks.add_task(send_email_task)
        
        return {"message": f"Laporan sedang diproses dan akan dikirim ke email {current_user.email}"}

    except Exception as e:
        logger.error(f"Gagal mengirim email laporan: {str(e)}")
        raise HTTPException(status_code=500, detail="Terjadi kesalahan saat mengirim email laporan")