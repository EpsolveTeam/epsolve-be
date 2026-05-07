from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from loguru import logger
from sqlalchemy.orm import Session

from app.db.session import engine
from app.models.report_setting import ReportSetting
from app.api.api_v1.endpoints.analytics import get_dashboard_summary
from app.services.email_service import send_analytics_report_email


PERIOD_DAYS = {"1w": 7, "1m": 30, "3m": 90}


def check_and_send_scheduled_reports() -> None:
    logger.info("Mengecek jadwal pengiriman report otomatis...")
    now = datetime.utcnow()

    with Session(engine) as db:
        active_settings = (
            db.query(ReportSetting).filter(ReportSetting.is_active == True).all()  # noqa: E712
        )

        for setting in active_settings:
            days_required = PERIOD_DAYS.get(setting.period, 30)
            last_sent_at: Optional[datetime] = setting.last_sent_at

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

# Dev / testing: cek setiap 1 menit
scheduler.add_job(check_and_send_scheduled_reports, "interval", minutes=1)

# Production option:
# scheduler.add_job(check_and_send_scheduled_reports, 'cron', hour=8, minute=0)

