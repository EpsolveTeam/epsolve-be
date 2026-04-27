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
        
def send_resolution_email(ticket_id: int, user_email: str, subject: str, solution: str):
    """
    Mengirim email ke Karyawan/Manajer saat tiket direspons oleh Helpdesk.
    """
    try:
        email_html = f"""
        <div style="font-family: sans-serif; color: #333;">
            <h2>Pembaruan Tiket #{ticket_id}</h2>
            <p>Halo,</p>
            <p>Tiket Anda dengan masalah <strong>"{subject}"</strong> telah direspons oleh tim Helpdesk.</p>
            <h3 style="color: #0051C3;">Solusi / Tanggapan:</h3>
            <p style="padding: 15px; border-left: 5px solid #0051C3; background-color: #f4f7f6;">
                {solution}
            </p>
            <p>Silakan login ke aplikasi Epsolve untuk detail lebih lanjut.</p>
            <p>Salam,<br><strong>Tim IT Helpdesk Epsolve</strong></p>
        </div>
        """

        resend.Emails.send({
            "from": "Epsolve Helpdesk <onboarding@resend.dev>", # Ganti domain nanti kalau sudah live
            "to": user_email,
            "subject": f"✅ Tiket #{ticket_id} Telah Direspons",
            "html": email_html
        })
        logger.info(f"Email resolusi untuk tiket #{ticket_id} berhasil dikirim ke {user_email}")
        
    except Exception as e:
        logger.error(f"Gagal mengirim email resolusi: {e}")