from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from loguru import logger

from app.db.session import get_session
from app.models.ticket import Ticket
from app.models.chat_log import ChatLog
from app.core.dependencies import require_admin
from app.models.user import User

router = APIRouter()

@router.get("/summary")
def get_analytics_summary(
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """
    Endpoint untuk menarik data analytics.
    Akan mereturn total tiket, status tiket, frekuensi masalah, dan metrik chat.
    """
    logger.info(f"Admin {current_user.email} mengambil data analytics.")
    
    try:
        total_tickets = db.query(func.count(Ticket.id)).scalar() or 0
        open_tickets = db.query(func.count(Ticket.id)).filter(Ticket.status == "open").scalar() or 0
        
        closed_tickets = db.query(func.count(Ticket.id)).filter(Ticket.status != "open").scalar() or 0

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
            "problem_frequency": problem_frequency,
            "chatbot_metrics": {
                "total_interactions": total_chats,
                "resolved_by_bot": resolved_by_bot
            }
        }
        
    except Exception as e:
        logger.error(f"Gagal mengambil data analytics: {str(e)}")
        raise HTTPException(status_code=500, detail="Terjadi kesalahan saat menghitung data analytics")