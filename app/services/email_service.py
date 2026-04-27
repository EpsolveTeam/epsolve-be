import requests
from app.core.config import settings
from loguru import logger

def send_email_via_brevo(to_email: str, subject: str, html_content: str):
    """Fungsi inti untuk menembak API Brevo."""
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": settings.BREVO_API_KEY,
        "content-type": "application/json"
    }
    payload = {
        "sender": {
            "name": "Epsolve IT Helpdesk", 
            "email": settings.BREVO_SENDER_EMAIL
        },
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_content
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code not in [200, 201, 202]:
            logger.error(f"Response Brevo API Error: {response.text}")
            raise Exception("Gagal mengirim email via Brevo")
    except Exception as e:
        logger.error(f"Error HTTP Request ke Brevo: {str(e)}")
        raise e

BASE_STYLE = "background-color: #f9f9fb; padding: 40px 20px; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;"
CARD_STYLE = "max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 40px; border-radius: 16px; border: 1px solid #eef0f2; text-align: center; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);"

def send_ticket_notification(admin_emails: list[str], ticket_id: int, user_email: str, subject: str, description: str):
    """Trigger email: Dikirim ke SEMUA Admin/Helpdesk yang ada di DB."""
    html_content = f"""
    <div style="{BASE_STYLE}">
        <div style="{CARD_STYLE}">
            <h2 style="color: #111827;">Notifikasi Tiket Baru</h2>
            </div>
    </div>
    """
    try:
        for email in admin_emails:
            send_email_via_brevo(
                to_email=email, 
                subject=f"[NEW TICKET #{ticket_id}] {subject}", 
                html_content=html_content
            )
        logger.info(f"Email notifikasi tiket #{ticket_id} dikirim ke {len(admin_emails)} admin")
    except Exception as e:
        logger.error(f"Gagal kirim notif tiket: {e}")

def send_resolution_email(ticket_id: int, user_email: str, subject: str, solution: str):
    """Trigger email: Saat Admin membalas tiket (Dikirim ke Karyawan)."""
    html_content = f"""
    <div style="{BASE_STYLE}">
        <div style="{CARD_STYLE}">
            <h2 style="color: #111827; margin-top: 0; font-size: 24px; letter-spacing: -0.5px;">Update Tiket <span style="color: #0051C3;">#{ticket_id}</span></h2>
            <p style="color: #6b7280; font-size: 15px; margin-bottom: 30px;">Halo, permintaan Anda mengenai <strong>"{subject}"</strong> telah selesai diproses.</p>

            <div style="text-align: left; margin-bottom: 30px;">
                <p style="color: #9ca3af; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;">Tanggapan Tim Helpdesk:</p>
                <div style="background-color: #f0f7ff; border-left: 4px solid #0051C3; padding: 20px; border-radius: 4px 12px 12px 4px; color: #1e293b; font-size: 15px; line-height: 1.6;">
                    {solution}
                </div>
            </div>

            <p style="color: #6b7280; font-size: 14px; margin-bottom: 25px;">Butuh bantuan lebih lanjut? Silakan login kembali.</p>
            <p style="color: #9ca3af; font-size: 13px; margin: 0; border-top: 1px solid #f1f5f9; padding-top: 20px;">Salam hangat,<br><strong>Tim IT Helpdesk Epsolve</strong></p>
        </div>
    </div>
    """
    try:
        send_email_via_brevo(to_email=user_email, subject=f"✅ Tiket #{ticket_id} Telah Direspons", html_content=html_content)
        logger.info(f"Email resolusi tiket #{ticket_id} berhasil dikirim")
    except Exception as e:
        logger.error(f"Gagal kirim email resolusi: {e}")

def send_analytics_report_email(user_email: str, user_name: str, report_data: dict):
    """Trigger email: Mengirim laporan Analytics ke Admin/Manajer."""
    metrics = report_data.get("ticket_metrics", {})
    chats = report_data.get("chatbot_metrics", {})
    
    success_rate = (chats.get("resolved_by_bot", 0) / chats.get("total_interactions", 1) * 100) if chats.get("total_interactions", 0) > 0 else 0
    
    problem_rows = ""
    for item in report_data.get("problem_frequency", [])[:5]:
        problem_rows += f"""
        <tr>
            <td style="padding: 12px 0; color: #4b5563; font-size: 14px; border-bottom: 1px solid #f1f5f9;">{item.get('category', 'Unknown')}</td>
            <td style="padding: 12px 0; color: #0051C3; font-size: 14px; font-weight: bold; text-align: right; border-bottom: 1px solid #f1f5f9;">{item.get('count', 0)}</td>
        </tr>"""

    html_content = f"""
    <div style="{BASE_STYLE}">
        <div style="{CARD_STYLE}">
            <h2 style="color: #111827; margin-top: 0; font-size: 26px;">Laporan Analytics</h2>
            <p style="color: #6b7280; font-size: 15px; margin-bottom: 35px;">Halo {user_name}, berikut adalah ringkasan performa Helpdesk.</p>

            <table width="100%" cellspacing="0" cellpadding="0" style="margin-bottom: 30px;">
                <tr>
                    <td width="48%" style="background-color: #f8fafc; border-radius: 12px; padding: 20px; text-align: center; border: 1px solid #f1f5f9;">
                        <span style="color: #6b7280; font-size: 12px; text-transform: uppercase;">Total Tiket</span><br>
                        <span style="color: #111827; font-size: 24px; font-weight: bold;">{metrics.get('total', 0)}</span>
                    </td>
                    <td width="4%"></td>
                    <td width="48%" style="background-color: #f8fafc; border-radius: 12px; padding: 20px; text-align: center; border: 1px solid #f1f5f9;">
                        <span style="color: #059669; font-size: 12px; text-transform: uppercase;">Bot Success</span><br>
                        <span style="color: #111827; font-size: 24px; font-weight: bold;">{success_rate:.1f}%</span>
                    </td>
                </tr>
            </table>

            <div style="text-align: left;">
                <h4 style="color: #111827; font-size: 16px; margin-bottom: 15px; border-bottom: 2px solid #f1f5f9; padding-bottom: 8px;">Kategori Terpopuler</h4>
                <table width="100%" cellspacing="0" cellpadding="0">
                    {problem_rows if problem_rows else '<tr><td style="color: #9ca3af; text-align: center; padding: 20px;">Belum ada data</td></tr>'}
                </table>
            </div>

            <p style="color: #9ca3af; font-size: 13px; margin-top: 40px;">Buka Dashboard Admin untuk analisis lebih mendalam.</p>
        </div>
    </div>
    """
    try:
        send_email_via_brevo(to_email=user_email, subject="📊 Ringkasan Laporan Helpdesk Epsolve", html_content=html_content)
        logger.info(f"Email laporan analytics berhasil dikirim ke {user_email}")
    except Exception as e:
        logger.error(f"Gagal kirim email laporan: {e}")