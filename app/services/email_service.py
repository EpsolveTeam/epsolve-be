import resend
from app.core.config import settings
from loguru import logger

resend.api_key = settings.RESEND_API_KEY

def send_ticket_notification(ticket_id: int, user_email: str, subject: str, description: str):
    try:
        params = {
            "from": settings.MAIL_FROM,
            "to": [settings.MAIL_TO],
            "subject": f"[NEW TICKET #{ticket_id}] {subject}",
            "html": f"""
                <h3>Notifikasi Tiket Baru - Epson Smart Helpdesk</h3>
                <p><strong>ID Tiket:</strong> {ticket_id}</p>
                <p><strong>Pengirim:</strong> {user_email}</p>
                <p><strong>Masalah:</strong> {description}</p>
                <br>
                <p>Mohon segera tindak lanjuti melalui Dashboard Admin.</p>
            """,
        }
        resend.Emails.send(params)
        logger.info(f"Email notifikasi tiket #{ticket_id} berhasil dikirim ke {settings.MAIL_TO}")
    except Exception as e:
        logger.error(f"Gagal mengirim email untuk tiket #{ticket_id}: {str(e)}")