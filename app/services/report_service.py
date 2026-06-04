from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.api.api_v1.endpoints.analytics import get_dashboard_summary
from app.models.ticket import Ticket


PERIOD_DAYS = {"7d": 7, "1w": 7, "1m": 30, "3m": 90}


def build_analytics_report_data(*, period: str, db: Session) -> Dict[str, Any]:
    """Bangun struktur `report_data` lengkap untuk PDF analytics.
    """

    now = datetime.now(timezone.utc)
    days = PERIOD_DAYS.get(period, 30)

    start_date = now - timedelta(days=days)
    start_date_naive = start_date.replace(tzinfo=None)

    tickets = db.query(Ticket).filter(Ticket.created_at >= start_date_naive).all()

    dashboard_summary = get_dashboard_summary(period=period, db=db, current_user=None)

    return {
        "period": period,
        "generated_at": now.strftime("%d/%m/%Y %H:%M"),
        "start_date": start_date.strftime("%d/%m/%Y"),
        "end_date": now.strftime("%d/%m/%Y"),
        "tickets": tickets,
        "ticket_metrics": dashboard_summary.get("ticket_metrics", {}),
        "chatbot_metrics": dashboard_summary.get("chatbot_metrics", {}),
        "problem_frequency": dashboard_summary.get("problem_frequency", []),
    }

