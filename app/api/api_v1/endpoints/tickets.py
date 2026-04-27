import uuid
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from loguru import logger
from supabase import create_client, Client
from pydantic import BaseModel
from app.services.email_service import send_ticket_notification, send_resolution_email

from app.db.session import get_session
from app.models.ticket import Ticket 
from app.models.user import User, UserRole
from app.core.config import settings
from app.core.dependencies import get_current_user

router = APIRouter()

supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
BUCKET_NAME = "helpdesk-files" 

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_ticket(
    user_email: str = Form(...),
    subject: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    division: str = Form(...),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Endpoint untuk membuat tiket baru + Upload Gambar ke Supabase Storage.
    Menggunakan Form-Data karena ada file upload.
    """
    logger.info(f"Menerima eskalasi tiket dari {user_email} (User ID: {current_user.id})")
    
    try:
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
            subject=subject,
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

        send_ticket_notification(
            ticket_id=new_ticket.id,
            user_email=new_ticket.user_email,
            subject=new_ticket.subject,
            description=new_ticket.description
        )
        
        return {
            "message": "Tiket berhasil dibuat dan notifikasi telah dikirim", 
            "ticket_id": new_ticket.id,
            "image_url": final_image_url
        }
    
    except Exception as e:
        logger.error(f"Gagal memproses tiket: {str(e)}")
        raise HTTPException(status_code=500, detail="Terjadi kesalahan pada server saat memproses tiket")

@router.get("/")
def get_tickets(
    status: Optional[str] = Query(None, description="Filter berdasarkan status tiket"),
    division: Optional[str] = Query(None, description="Filter berdasarkan divisi"),
    category: Optional[str] = Query(None, description="Filter berdasarkan kategori masalah"),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
     Mengambil daftar tiket. 
     Karyawan hanya melihat tiketnya sendiri. Admin/Helpdesk melihat semua.
     Mendukung filter query parameter (?status=...&division=...)
     """
    query = db.query(Ticket)
    
    if current_user.role == UserRole.KARYAWAN:
        query = query.filter(Ticket.user_id == current_user.id)

    if status:
        query = query.filter(Ticket.status == status)
    if division:
        query = query.filter(Ticket.division == division)
    if category:
        query = query.filter(Ticket.category == category)
        
    tickets = query.order_by(Ticket.created_at.desc()).all()
    return tickets

class TicketUpdate(BaseModel):
    status: Optional[str] = None
    admin_response: Optional[str] = None

@router.patch("/{ticket_id}")
def update_ticket(
    ticket_id: int, 
    ticket_in: TicketUpdate, 
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Fitur bagi Admin/Helpdesk untuk merespons dan mengubah status tiket.
    """
    if current_user.role == UserRole.KARYAWAN:
        raise HTTPException(status_code=403, detail="Anda tidak memiliki akses untuk membalas tiket.")

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
            subject=ticket.subject,
            solution=ticket.admin_response
        )

    db.commit()
    db.refresh(ticket)

    logger.info(f"Tiket #{ticket_id} diperbarui oleh Admin.")
    return {"message": f"Tiket #{ticket_id} berhasil diperbarui", "data": ticket}