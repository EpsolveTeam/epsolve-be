from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from loguru import logger
from sqlalchemy.orm import Session

from app.db.session import engine
from app.models.report_setting import ReportSetting
from app.api.api_v1.endpoints.analytics import get_dashboard_summary
from app.services.email_service import send_analytics_report_email


PERIOD_DAYS = {"1w": 7, "1m": 30, "3m": 90}

# For testing: override period to send faster (in minutes)
# Set SCHEDULER_TEST_PERIOD_MINUTES=1 to make "1w" send every 1 minute
TEST_PERIOD_MINUTES = int(os.getenv("SCHEDULER_TEST_PERIOD_MINUTES", "0"))


def get_days_required(period: str) -> float:
    """Get days required for a period, with optional test override."""
    if TEST_PERIOD_MINUTES > 0 and period == "1w":
        return TEST_PERIOD_MINUTES / (60 * 24)  # Convert minutes to days
    return PERIOD_DAYS.get(period, 30)


def check_and_send_scheduled_reports() -> None:
    logger.info("Mengecek jadwal pengiriman report otomatis...")
    now = datetime.now(timezone.utc)

    with Session(engine) as db:
        active_settings = (
            db.query(ReportSetting).filter(ReportSetting.is_active == True).all()  # noqa: E712
        )

        for setting in active_settings:
            days_required = get_days_required(setting.period)
            last_sent_at: Optional[datetime] = setting.last_sent_at

            # Ensure last_sent_at is timezone-aware for comparison
            if last_sent_at and last_sent_at.tzinfo is None:
                last_sent_at = last_sent_at.replace(tzinfo=timezone.utc)

            due = (not last_sent_at) or ((now - last_sent_at) >= timedelta(days=days_required))
            if not due:
                continue

            logger.info(
                f"Waktunya mengirim report ke {setting.recipient_email} (Periode: {setting.period})"
            )

            try:
                report_data = get_dashboard_summary(
                    period=setting.period,
                    db=db,
                    current_user=None,
                )

                send_analytics_report_email(
                    user_email=setting.recipient_email,
                    user_name="Administrator",
                    report_data=report_data,
                )

                setting.last_sent_at = now
                db.commit()

                logger.success(
                    f"Report berhasil dikirim otomatis ke {setting.recipient_email}"
                )
            except Exception as e:
                db.rollback()
                logger.error(
                    f"Gagal mengirim report otomatis ke {setting.recipient_email}: {e}"
                )


scheduler = BackgroundScheduler()

# Production: cek setiap hari pukul 8 pagi
scheduler.add_job(check_and_send_scheduled_reports, 'cron', hour=8, minute=0)

# Development option (uncomment for testing):
# scheduler.add_job(check_and_send_scheduled_reports, "interval", minutes=1)

