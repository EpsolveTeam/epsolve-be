from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.session import get_session
from app.models.ticket import Ticket 
from pydantic import BaseModel
from loguru import logger
from app.services.email_service import send_ticket_notification

router = APIRouter()

class TicketCreate(BaseModel):
    user_email: str
    subject: str
    description: str
    category: str # diisi: Hardware / Firmware / Quality Printing / Part Problem
    image_url: Optional[str] = None

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_ticket(ticket_in: TicketCreate, db: Session = Depends(get_session)):
    """
    Endpoint untuk membuat tiket baru (Eskalasi) dan mengirim notifikasi email[cite: 129, 267].
    """
    logger.info(f"Menerima eskalasi tiket kategori {ticket_in.category} dari {ticket_in.user_email}")
    
    try:
        new_ticket = Ticket(
            user_email=ticket_in.user_email,
            subject=ticket_in.subject,
            description=ticket_in.description,
            category=ticket_in.category,
            image_url=ticket_in.image_url,
            status="open"
        )
        db.add(new_ticket)
        db.commit()
        db.refresh(new_ticket)
        
        logger.success(f"Tiket #{new_ticket.id} berhasil disimpan di database.")

        send_ticket_notification(
            ticket_id=new_ticket.id,
            user_email=new_ticket.user_email,
            subject=new_ticket.subject,
            description=new_ticket.description
        )
        
        return {"message": "Tiket berhasil dibuat dan notifikasi telah dikirim", "ticket_id": new_ticket.id}
    
    except Exception as e:
        logger.error(f"Gagal memproses tiket: {str(e)}")
        raise HTTPException(status_code=500, detail="Terjadi kesalahan pada server")

@router.get("/", response_model=List[Ticket])
def read_tickets(db: Session = Depends(get_session)):
    """
    Endpoint untuk Admin/Helpdesk melihat semua tiket
    """
    logger.info("Admin mengakses seluruh daftar tiket.")
    return db.query(Ticket).all()

class TicketUpdate(BaseModel):
    status: Optional[str] = None
    admin_response: Optional[str] = None

@router.patch("/{ticket_id}")
def update_ticket(
    ticket_id: int, 
    ticket_in: TicketUpdate, # Gunakan schema baru
    db: Session = Depends(get_session)
    ):
    """
    Fitur bagi Admin/Helpdesk untuk merespons dan mengubah status tiket.
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        logger.error(f"Gagal update: Tiket #{ticket_id} tidak ditemukan.")
        raise HTTPException(status_code=404, detail="Tiket tidak ditemukan")
    
    old_status = ticket.status
    # Update field yang dikirim saja
    if ticket_in.status is not None:
        ticket.status = ticket_in.status
        
    if ticket_in.admin_response is not None:
        ticket.admin_response = ticket_in.admin_response
        # Otomatis ubah status jadi 'answered' / 'closed' jika dibalas?
        # ticket.status = "answered" 
        
    db.commit()
    db.refresh(ticket)
    
    logger.info(f"Tiket #{ticket_id} diperbarui. Status: {old_status} -> {ticket.status}")
    return {"message": f"Tiket #{ticket_id} berhasil diperbarui", "data": ticket}