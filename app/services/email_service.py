import requests
import io
import uuid
from datetime import datetime, timedelta
from sqlmodel import create_engine, Session as SQLModelSession
from supabase import create_client, Client
from app.core.config import settings
from loguru import logger
from app.models.ticket import Ticket

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.units import inch
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

engine = create_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)

supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
REPORTS_BUCKET = "helpdesk-files"

BASE_STYLE = "background-color: #f9f9fb; padding: 40px 20px; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;"
CARD_STYLE = "max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 40px; border-radius: 16px; border: 1px solid #eef0f2; text-align: center; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);"


def send_email_via_brevo(to_email: str, subject: str, html_content: str, attachments: list = None):
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
    if attachments:
        payload["attachments"] = attachments
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code not in [200, 201, 202]:
            logger.error(f"Response Brevo API Error: {response.text}")
            raise Exception("Gagal mengirim email via Brevo")
    except Exception as e:
        logger.error(f"Error HTTP Request ke Brevo: {str(e)}")
        raise e


def send_password_reset_email(user_email: str, user_name: str, reset_url: str):
    html_content = f"""
    <div style="{BASE_STYLE}">
      <div style="{CARD_STYLE}">
        <h2 style="font-size:22px;font-weight:700;color:#1a1a2e;margin-bottom:8px;">Reset Password</h2>
        <p style="color:#555;font-size:15px;margin-bottom:8px;">Halo, <strong>{user_name}</strong>.</p>
        <p style="color:#555;font-size:14px;margin-bottom:24px;">
          Kami menerima permintaan untuk mereset password akun Epsolve Anda.<br>
          Klik tombol di bawah untuk membuat password baru.
        </p>
        <a href="{reset_url}" style="display:inline-block;background:#6366f1;color:#fff;text-decoration:none;padding:12px 28px;border-radius:8px;font-size:15px;font-weight:600;margin-bottom:24px;">
          Reset Password
        </a>
        <p style="color:#888;font-size:12px;margin-top:16px;">
          Link ini akan kadaluarsa dalam <strong>1 jam</strong>.<br>
          Jika Anda tidak merasa meminta reset password, abaikan email ini.
        </p>
      </div>
    </div>
    """
    send_email_via_brevo(user_email, "Reset Password - Epsolve Helpdesk", html_content)


def send_ticket_notification(admin_emails: list[str], ticket_id: int, user_email: str, description: str, category: str):
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
                subject=f"[NEW TICKET #{ticket_id}]", 
                html_content=html_content
            )
        logger.info(f"Email notifikasi tiket #{ticket_id} dikirim ke {len(admin_emails)} admin")
    except Exception as e:
        logger.error(f"Gagal kirim notif tiket: {e}")


def send_resolution_email(ticket_id: int, user_email: str, description: str, solution: str):
    """Trigger email: Saat Admin membalas tiket (Dikirim ke Karyawan)."""
    html_content = f"""
    <div style="{BASE_STYLE}">
        <div style="{CARD_STYLE}">
            <h2 style="color: #111827; margin-top: 0; font-size: 24px; letter-spacing: -0.5px;">Update Tiket <span style="color: #0051C3;">#{ticket_id}</span></h2>
            <p style="color: #6b7280; font-size: 15px; margin-bottom: 30px;">Halo, permintaan Anda telah selesai diproses.</p>

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
    """
    Mengirim laporan Analytics ke email tujuan dengan link download PDF.
    Generate PDF → Upload ke Supabase → Kirim email dengan signed URL.
    """
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

    button_style = "display: inline-block; background-color: #0051C3; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 14px; margin-top: 20px;"

    now = datetime.utcnow()
    start_date = (now - timedelta(days=30)).strftime("%d%m%Y")
    end_date = now.strftime("%d%m%Y")
    filename = f"Laporan_{start_date}-{end_date}.pdf"
    
    download_url = None
    try:
        pdf_bytes = generate_analytics_pdf({
            "period": "1m",
            "generated_at": now.strftime("%d/%m/%Y %H:%M"),
            "start_date": (now - timedelta(days=30)).strftime("%d/%m/%Y"),
            "end_date": now.strftime("%d/%m/%Y"),
            "tickets": []
        })
        logger.info(f"PDF generated: {len(pdf_bytes)} bytes")
        
        try:
            buckets = supabase.storage.list_buckets()
            bucket_exists = any(bucket.name == REPORTS_BUCKET for bucket in buckets)
            if not bucket_exists:
                supabase.storage.create_bucket(REPORTS_BUCKET, {"public": False})
                logger.info(f"Created Supabase bucket: {REPORTS_BUCKET}")
        except Exception as e:
            logger.warning(f"Bucket check failed (may exist): {e}")
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        file_path = f"analytics/{filename}"
        
        supabase.storage.from_(REPORTS_BUCKET).upload(
            path=file_path,
            file=pdf_bytes,
            file_options={"content-type": "application/pdf"}
        )
        logger.info(f"PDF uploaded to Supabase: {file_path}")
        
        signed_url_response = supabase.storage.from_(REPORTS_BUCKET).create_signed_url(
            path=file_path,
            expires_in=604800
        )
        download_url = signed_url_response.get('signedURL') or signed_url_response.get('signed_url')
        if not download_url:
            raise ValueError(f"No signed URL in response: {signed_url_response}")
        logger.info(f"Signed URL generated: {download_url}")
        
    except Exception as e:
        logger.error(f"Failed to prepare PDF/upload: {e}")
        download_url = None

    if download_url:
        download_section = f'''
        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #f1f5f9;">
            <a href="{download_url}" target="_blank" style="{button_style}">Download Laporan PDF</a>
            <p style="color: #9ca3af; font-size: 12px; margin-top: 15px; margin-bottom: 0;">Link aktif selama 7 hari. Klik tombol di atas untuk mengunduh file.</p>
        </div>
        '''
    else:
        download_section = '''
        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #f1f5f9;">
            <p style="color: #ef4444; font-size: 14px; font-weight: bold;">⚠️ Gagal menyiapkan laporan PDF</p>
            <p style="color: #9ca3af; font-size: 12px; margin-top: 10px; margin-bottom: 0;">Silakan hubungi administrator atau coba lagi nanti.</p>
        </div>
        '''

    html_content = f"""
    <div style="{BASE_STYLE}">
        <div style="{CARD_STYLE}">
            <h2 style="color: #111827; margin-top: 0; font-size: 26px;">Laporan Analytics</h2>
            <p style="color: #6b7280; font-size: 15px; margin-bottom: 35px;">Halo {user_name}, berikut adalah ringkasan performa Helpdesk.</p>

            <table width="100%" cellspacing="0" cellpadding="0" style="margin-bottom: 30px;">
                <tr>
                    <td width="48%" style="background-color: #f8fafc; border-radius: 12px; padding: 20px; text-align: center; border: 1px solid #f1f5f9;">
                        <span style="color: #6b7280; font-size: 12px; text-transform: uppercase;">Total Tiket</span><br>
                        <span style="color: #111827; font-size: 24px; font-weight: bold;">{metrics.get('total_escalations', 0)}</span>
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

            {download_section}

        </div>
    </div>
    """
    
    try:
        send_email_via_brevo(to_email=user_email, subject="📊 Ringkasan Laporan Helpdesk Epsolve", html_content=html_content)
        logger.info(f"Email laporan analytics berhasil dikirim ke {user_email}")
    except Exception as e:
        logger.error(f"Gagal kirim email laporan: {e}")


def generate_analytics_pdf(report_data: dict) -> bytes:
    """
    Generate PDF report from ticket data and return as bytes.
    Format: Laporan_DDMMYYYY-DDMMYYYY.pdf
    """
    if not PDF_AVAILABLE:
        logger.error("ReportLab not installed. Cannot generate PDF.")
        raise Exception("ReportLab library required for PDF generation")
    
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=letter)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=1,
        textColor=colors.darkblue
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        textColor=colors.darkblue
    )
    normal_style = styles['Normal']
    
    title = Paragraph("Laporan Analytics Helpdesk", title_style)
    elements.append(title)
    elements.append(Spacer(1, 12))
    
    period_info = f"Periode: {report_data.get('start_date', '-')} - {report_data.get('end_date', '-')}"
    generated_info = f"Dibuat: {report_data.get('generated_at', '-')}"
    
    elements.append(Paragraph(period_info, normal_style))
    elements.append(Paragraph(generated_info, normal_style))
    elements.append(Spacer(1, 20))
    
    tickets = report_data.get('tickets', [])
    ticket_metrics = report_data.get('ticket_metrics', {})
    chatbot_metrics = report_data.get('chatbot_metrics', {})

    if ticket_metrics:
        elements.append(Paragraph("Ringkasan Tiket", heading_style))
        summary_data = [
            ["Metric", "Nilai"],
            ["Total pertanyaan", str(ticket_metrics.get("total_questions", "-"))],
            ["Total eskalasi", str(ticket_metrics.get("total_escalations", "-"))],
            ["Tren pertanyaan", ticket_metrics.get("questions_trend", {}).get("text", "-")],
            ["Tren eskalasi", ticket_metrics.get("escalations_trend", {}).get("text", "-")],
            ["Persentase penyelesaian", f"{ticket_metrics.get('resolution_rate', 0)}%"],
            ["Tren penyelesaian", ticket_metrics.get("resolution_trend", {}).get("text", "-")],
            ["Rata-rata waktu penyelesaian", ticket_metrics.get("avg_resolution_time", "-")],
            ["Tren waktu rata-rata", ticket_metrics.get("avg_resolution_time_trend", {}).get("text", "-")],
        ]
        table = Table(summary_data, colWidths=[2.5*inch, 3.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.beige]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 16))

    if chatbot_metrics:
        elements.append(Paragraph("Ringkasan Chatbot", heading_style))
        chatbot_data = [
            ["Metric", "Nilai"],
            ["Total Interaksi", str(chatbot_metrics.get("total_sessions", "-"))],
            ["Tren Interaksi", chatbot_metrics.get("sessions_trend", {}).get("text", "-")],
            ["Persentase penyelesaian", f"{chatbot_metrics.get('resolution_rate', 0)}%"],
            ["Tren penyelesaian", chatbot_metrics.get("resolution_trend", {}).get("text", "-")],
        ]
        table = Table(chatbot_data, colWidths=[2.5*inch, 3.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.beige]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 16))


    chart_data = report_data.get('chart_data', [])
    if chart_data:
        elements.append(Paragraph("Data Per Hari (Ticket)", heading_style))
        chart_rows = [["Tanggal", "Jumlah Ticket"]]
        for row in chart_data[:31]:
            chart_rows.append([
                str(row.get('date', '-')),
                str(row.get('count', '-')),
            ])
        table = Table(chart_rows, colWidths=[2.6*inch, 3.4*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.beige]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 16))

    if report_data.get('problem_frequency'):
        elements.append(Paragraph("Frekuensi Masalah Teratas", heading_style))
        freq_data = [["Kategori", "Jumlah Tiket", "Jumlah Chat", "Tingkat Eskalasi"]]
        for item in report_data.get('problem_frequency', [])[:8]:
            freq_data.append([
                item.get('category', '-'),
                str(item.get('ticket_count', '-')),
                str(item.get('chat_count', '-')),
                item.get('escalation_rate', '-')
            ])
        table = Table(freq_data, colWidths=[2.5*inch, 1*inch, 1*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.beige]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 16))

    heading = Paragraph("Daftar Tiket", heading_style)

    elements.append(heading)
    elements.append(Spacer(1, 8))
    
    if tickets:
        table_data = [["ID", "Email", "Kategori", "Status", "Tanggal"]]
        for t in tickets[:100]:
            table_data.append([
                str(t.id),
                t.user_email[:20] + "..." if len(t.user_email) > 20 else t.user_email,
                t.category or "-",
                t.status or "-",
                t.created_at.strftime("%d/%m/%Y") if t.created_at else "-"
            ])
        
        table = Table(table_data, colWidths=[0.5*inch, 1.5*inch, 2*inch, 1*inch, 0.8*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("Tidak ada data tiket.", normal_style))
    

    doc.build(elements)

    output.seek(0)
    return output.getvalue()

