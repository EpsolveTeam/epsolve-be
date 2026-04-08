from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.db.session import get_session
from app.models.ticket import Ticket 
from pydantic import BaseModel

router = APIRouter()

class TicketCreate(BaseModel):
    user_email: str
    subject: str
    description: str
    printer_series: str

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_ticket(ticket_in: TicketCreate, db: Session = Depends(get_session)):
    """
    Endpoint untuk membuat tiket baru
    """
    new_ticket = Ticket(
        user_email=ticket_in.user_email,
        subject=ticket_in.subject,
        description=ticket_in.description,
        printer_series=ticket_in.printer_series,
        status="open"
    )
    db.add(new_ticket)
    db.commit()
    db.refresh(new_ticket)
    # in the future BE bisa minta Resend API untuk notifikasi email
    return {"message": "Tiket berhasil dibuat", "ticket_id": new_ticket.id}

@router.get("/", response_model=List[Ticket])
def read_tickets(db: Session = Depends(get_session)):
    """
    Endpoint untuk Admin/Helpdesk melihat semua tiket
    """
    tickets = db.query(Ticket).all()
    return tickets