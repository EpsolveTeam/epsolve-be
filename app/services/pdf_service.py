from __future__ import annotations

import io
from datetime import datetime
from typing import Any, Dict, List

from loguru import logger

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.units import inch

    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


def generate_analytics_pdf(report_data: dict) -> bytes:
    """Generate analytics PDF from `report_data`.

    Fungsi ini dipakai oleh:
    - endpoint download PDF (modal "Bagikan Laporan Analisis Periode Ini")
    - email/scheduler (signed URL)

    Pastikan struktur `report_data` berisi:
    - start_date, end_date, generated_at
    - tickets
    - ticket_metrics, chatbot_metrics
    - chart_data, problem_frequency (opsional)
    """

    if not PDF_AVAILABLE:
        logger.error("ReportLab not installed. Cannot generate PDF.")
        raise Exception("ReportLab library required for PDF generation")

    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=letter)
    elements: List[Any] = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=18,
        spaceAfter=30,
        alignment=1,
        textColor=colors.darkblue,
    )
    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=14,
        spaceAfter=12,
        textColor=colors.darkblue,
    )
    normal_style = styles["Normal"]

    title = Paragraph("Laporan Analytics Helpdesk", title_style)
    elements.append(title)
    elements.append(Spacer(1, 12))

    period_info = f"Periode: {report_data.get('start_date', '-')} - {report_data.get('end_date', '-')}"
    generated_info = f"Dibuat: {report_data.get('generated_at', '-') }"

    elements.append(Paragraph(period_info, normal_style))
    elements.append(Paragraph(generated_info, normal_style))
    elements.append(Spacer(1, 20))

    tickets = report_data.get("tickets", [])
    ticket_metrics: Dict[str, Any] = report_data.get("ticket_metrics", {})
    chatbot_metrics: Dict[str, Any] = report_data.get("chatbot_metrics", {})

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
        table = Table(summary_data, colWidths=[2.5 * inch, 3.5 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("FONTSIZE", (0, 1), (-1, -1), 9),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.beige]),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]
            )
        )
        elements.append(table)
        elements.append(Spacer(1, 16))

    if chatbot_metrics:
        elements.append(Paragraph("Ringkasan Chatbot", heading_style))
        chatbot_data = [
            ["Metric", "Nilai"],
            ["Total Interaksi", str(chatbot_metrics.get("total_sessions", "-"))],
            ["Tren Interaksi", chatbot_metrics.get("sessions_trend", {}).get("text", "-" )],
            ["Persentase penyelesaian", f"{chatbot_metrics.get('resolution_rate', 0)}%"],
            ["Tren penyelesaian", chatbot_metrics.get("resolution_trend", {}).get("text", "-")],
        ]
        table = Table(chatbot_data, colWidths=[2.5 * inch, 3.5 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("FONTSIZE", (0, 1), (-1, -1), 9),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.beige]),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]
            )
        )
        elements.append(table)
        elements.append(Spacer(1, 16))

    chart_data = report_data.get("chart_data", [])
    if chart_data:
        elements.append(Paragraph("Data Per Hari (Ticket)", heading_style))
        chart_rows = [["Tanggal", "Jumlah Ticket"]]
        for row in chart_data[:31]:
            chart_rows.append(
                [
                    str(row.get("date", "-")),
                    str(row.get("count", "-")),
                ]
            )
        table = Table(chart_rows, colWidths=[2.6 * inch, 3.4 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("FONTSIZE", (0, 1), (-1, -1), 8),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.beige]),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]
            )
        )
        elements.append(table)
        elements.append(Spacer(1, 16))

    if report_data.get("problem_frequency"):
        elements.append(Paragraph("Frekuensi Masalah Teratas", heading_style))
        freq_data = [["Kategori", "Jumlah Tiket", "Jumlah Chat", "Tingkat Eskalasi"]]
        for item in report_data.get("problem_frequency", [])[:8]:
            freq_data.append(
                [
                    item.get("category", "-"),
                    str(item.get("ticket_count", "-")),
                    str(item.get("chat_count", "-")),
                    item.get("escalation_rate", "-"),
                ]
            )
        table = Table(freq_data, colWidths=[2.5 * inch, 1 * inch, 1 * inch, 1.5 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("FONTSIZE", (0, 1), (-1, -1), 8),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.beige]),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]
            )
        )
        elements.append(table)
        elements.append(Spacer(1, 16))

    elements.append(Paragraph("Daftar Tiket", heading_style))
    elements.append(Spacer(1, 8))

    if tickets:
        table_data = [["ID", "Email", "Kategori", "Status", "Tanggal"]]
        for t in tickets[:100]:
            table_data.append(
                [
                    str(t.id),
                    t.user_email[:20] + "..." if len(t.user_email) > 20 else t.user_email,
                    t.category or "-",
                    t.status or "-",
                    t.created_at.strftime("%d/%m/%Y") if t.created_at else "-",
                ]
            )

        table = Table(table_data, colWidths=[0.5 * inch, 1.5 * inch, 2 * inch, 1 * inch, 0.8 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 9),
                    ("FONTSIZE", (0, 1), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]
            )
        )
        elements.append(table)
    else:
        elements.append(Paragraph("Tidak ada data tiket.", normal_style))

    doc.build(elements)
    output.seek(0)
    return output.getvalue()

