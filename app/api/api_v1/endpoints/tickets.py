import uuid
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from typing import Optional
from loguru import logger
from supabase import create_client, Client
from pydantic import BaseModel
from app.services.email_service import send_ticket_notification, send_resolution_email

from app.db.session import get_session
from app.models.ticket import Ticket
from app.models.user import User, UserRole
from app.core.config import settings
from app.core.dependencies import require_karyawan, require_helpdesk, get_current_user

router = APIRouter()

supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
BUCKET_NAME = "helpdesk-files"


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_ticket(
    user_email: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    division: str = Form(...),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_session),
    current_user: User = Depends(require_karyawan),
):
    """
    Endpoint untuk membuat tiket baru + Upload Gambar ke Supabase Storage.
    Menggunakan Form-Data karena ada file upload.
    """
    logger.info(f"Menerima eskalasi tiket kategori {category} dari {current_user.email}")

    try:
        # Validasi: pastikan user_email yang di-submit sesuai dengan user yang sedang login
        if user_email != current_user.email:
            logger.error(f"Email form ({user_email}) tidak cocok dengan email user login ({current_user.email})")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email pengaju tidak valid"
            )
        
        final_image_url = None

        if image:
            file_bytes = image.file.read()
            file_extension = image.filename.split(".")[-1]
            unique_filename = f"tickets/{uuid.uuid4()}.{file_extension}"

            supabase.storage.from_(BUCKET_NAME).upload(
                path=unique_filename,
                file=file_bytes,
                file_options={"content-type": image.content_type}
            )

            final_image_url = supabase.storage.from_(BUCKET_NAME).get_public_url(unique_filename)
            logger.info(f"Gambar berhasil diupload: {final_image_url}")

        new_ticket = Ticket(
            user_id=current_user.id,
            user_email=user_email,
            description=description,
            category=category,
            division=division,
            image_url=final_image_url,
            status="open"
        )

        db.add(new_ticket)
        db.commit()
        db.refresh(new_ticket)

        logger.success(f"Tiket #{new_ticket.id} berhasil disimpan.")

        admins = db.query(User).filter(
            User.role.in_([UserRole.ADMIN, UserRole.HELPDESK])
        ).all()
        
        admin_emails = [admin.email for admin in admins]

        if admin_emails:
            send_ticket_notification(
                admin_emails=admin_emails,
                ticket_id=new_ticket.id,
                user_email=new_ticket.user_email,
                description=new_ticket.description,
                category=new_ticket.category
            )
        else:
            logger.warning("Tiket dibuat, tapi tidak ada Admin/Helpdesk ditemukan di DB untuk dikirimi notifikasi.")

        return {
            "message": "Tiket berhasil dibuat dan notifikasi telah dikirim",
            "ticket_id": new_ticket.id,
            "user_name": current_user.full_name,
            "user_email": new_ticket.user_email,
            "description": new_ticket.description,
            "category": new_ticket.category,
            "division": new_ticket.division,
            "status": new_ticket.status,
            "image_url": final_image_url
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Gagal memproses tiket: {str(e)}")
        db.rollback() 
        raise HTTPException(status_code=500, detail="Terjadi kesalahan pada server")


@router.get("/")
def get_tickets(
    status: Optional[str] = Query(None, description="Filter berdasarkan status tiket: open, answered, closed"),
    is_answered: Optional[bool] = Query(None, description="Filter berdasarkan status terjawab: true=answered, false=open"),
    division: Optional[str] = Query(None, description="Filter berdasarkan divisi"),
    category: Optional[str] = Query(None, description="Filter berdasarkan kategori masalah"),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
     Mengambil daftar tiket. 
     Karyawan hanya melihat tiketnya sendiri. Admin/Helpdesk melihat semua.
     Mendukung filter query parameter (?status=...&division=...&is_answered=true/false)
     """
    query = db.query(Ticket)

    if current_user.role == UserRole.KARYAWAN:
        query = query.filter(Ticket.user_id == current_user.id)
    elif current_user.role not in (UserRole.HELPDESK, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    if status:
        query = query.filter(Ticket.status == status)
    if is_answered is not None:
        if is_answered:
            query = query.filter(Ticket.status.in_(["answered", "closed"]))
        else:
            query = query.filter(Ticket.status == "open")
    if division:
        query = query.filter(Ticket.division == division)
    if category:
        query = query.filter(Ticket.category == category)

    tickets = query.order_by(Ticket.created_at.desc()).all()
    
    result = []
    for t in tickets:
        user = db.query(User).filter(User.id == t.user_id).first() if t.user_id else None
        result.append({
            "id": t.id,
            "description": t.description,
            "category": t.category,
            "division": t.division,
            "user_email": t.user_email,
            "user_name": user.full_name if user else None,
            "status": t.status,
            "admin_response": t.admin_response,
            "image_url": t.image_url,
            "created_at": t.created_at
        })
    
    return result


class TicketUpdate(BaseModel):
    status: Optional[str] = None
    admin_response: Optional[str] = None


@router.patch("/{ticket_id}")
def update_ticket(
    ticket_id: int,
    ticket_in: TicketUpdate,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_helpdesk),
):
    """
    Fitur bagi Admin/Helpdesk untuk merespons dan mengubah status tiket.
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        logger.error(f"Gagal update: Tiket #{ticket_id} tidak ditemukan.")
        raise HTTPException(status_code=404, detail="Tiket tidak ditemukan")

    old_status = ticket.status

    if ticket_in.admin_response is not None:
        ticket.admin_response = ticket_in.admin_response

        if ticket_in.status is None and old_status == "open":
            ticket.status = "answered"

        send_resolution_email(
            ticket_id=ticket.id,
            user_email=ticket.user_email,
            description=ticket.description,
            solution=ticket.admin_response
        )

    if ticket_in.status is not None:
        ticket.status = ticket_in.status

    db.commit()
    db.refresh(ticket)

    logger.info(f"Tiket #{ticket_id} diperbarui oleh {current_user.email}. Status: {old_status} -> {ticket.status}")
    return {"message": f"Tiket #{ticket_id} berhasil diperbarui", "data": ticket}