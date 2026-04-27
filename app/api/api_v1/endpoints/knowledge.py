from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from loguru import logger

from app.db.session import get_session
from app.models.knowledge import KnowledgeBase
from app.models.ticket import Ticket
from app.models.user import User
from app.core.dependencies import require_karyawan, require_admin

router = APIRouter()

class KnowledgeCreate(BaseModel):
    title: str
    content: str
    category: str

class KnowledgeResponse(BaseModel):
    id: int
    title: str
    content: str
    category: str

    class Config:
        from_attributes = True

class KnowledgeUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None


@router.post("/", response_model=KnowledgeResponse, status_code=status.HTTP_201_CREATED)
def create_knowledge(
    kb_in: KnowledgeCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """
    Endpoint untuk Admin menambahkan data Knowledge Base baru (Create).
    """
    logger.info(f"Admin {current_user.email} menambahkan knowledge base baru: {kb_in.title} ({kb_in.category})")

    try:
        # TODO: integrasi fungsi OpenAI untuk mengubah 'kb_in.content' menjadi Vector (embedding)
        new_kb = KnowledgeBase(
            title=kb_in.title,
            content=kb_in.content,
            category=kb_in.category
            # embedding=... (diisi modul AI)
        )

        db.add(new_kb)
        db.commit()
        db.refresh(new_kb)

        logger.success(f"Knowledge Base ID #{new_kb.id} berhasil disimpan.")
        return new_kb

    except Exception as e:
        logger.error(f"Gagal menyimpan knowledge base: {str(e)}")
        raise HTTPException(status_code=500, detail="Terjadi kesalahan pada server")


@router.get("/", response_model=List[KnowledgeResponse])
def get_all_knowledge(
    category: Optional[str] = Query(None, description="Filter kategori"),
    division: Optional[str] = Query(None, description="Filter divisi"),
    db: Session = Depends(get_session),
    current_user: User = Depends(require_karyawan),
):
    """
    Endpoint untuk READ semua data Knowledge Base.
    Bisa difilter berdasarkan kategori dan jenis produk.
    """
    logger.info(f"User {current_user.email} mengambil daftar Knowledge Base.")

    query = db.query(KnowledgeBase)
    if category:
        query = query.filter(KnowledgeBase.category == category)
    if division:
        query = query.filter(KnowledgeBase.division == division) 
    return query.all()


@router.get("/{kb_id}", response_model=KnowledgeResponse)
def get_knowledge_by_id(
    kb_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_karyawan),
):
    """
    Endpoint untuk melihat detail satu Knowledge Base berdasarkan ID.
    """
    kb_data = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()

    if not kb_data:
        logger.warning(f"User {current_user.email} mencoba akses Knowledge Base ID #{kb_id} yang tidak ditemukan.")
        raise HTTPException(status_code=404, detail="Data Knowledge Base tidak ditemukan")

    return kb_data


@router.delete("/{kb_id}")
def delete_knowledge(
    kb_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """
    Endpoint untuk DELETE Knowledge Base.
    """
    kb_data = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()

    if not kb_data:
        raise HTTPException(status_code=404, detail="Data Knowledge Base tidak ditemukan")

    db.delete(kb_data)
    db.commit()
    logger.success(f"Knowledge Base ID #{kb_id} berhasil dihapus oleh {current_user.email}.")

    return {"message": f"Knowledge Base ID #{kb_id} berhasil dihapus"}


@router.put("/{kb_id}", response_model=KnowledgeResponse)
def update_knowledge(
    kb_id: int,
    kb_in: KnowledgeUpdate,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """
    Endpoint untuk UPDATE data Knowledge Base.
    """
    kb_data = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()

    if not kb_data:
        raise HTTPException(status_code=404, detail="Data Knowledge Base tidak ditemukan")

    if kb_in.title is not None:
        kb_data.title = kb_in.title
    if kb_in.content is not None:
        kb_data.content = kb_in.content
        # TODO: Jika content berubah, trigger ulang OpenAI untuk update 'embedding'-nya
    if kb_in.category is not None:
        kb_data.category = kb_in.category

    db.commit()
    db.refresh(kb_data)

    logger.info(f"Knowledge Base ID #{kb_id} berhasil diperbarui oleh {current_user.email}.")
    return kb_data


@router.post("/from-ticket/{ticket_id}", status_code=status.HTTP_201_CREATED)
def create_kb_from_ticket(
    ticket_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """
    Mengubah tiket yang sudah diselesaikan menjadi artikel Knowledge Base.
    """
    logger.info(f"Admin {current_user.email} mengkonversi tiket #{ticket_id} menjadi Knowledge Base")

    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Tiket tidak ditemukan.")

    if not ticket.admin_response:
        raise HTTPException(
            status_code=400,
            detail="Tiket ini belum memiliki balasan dari admin. Tidak bisa dijadikan Knowledge Base."
        )

    kb_content = f"**Keluhan Pelanggan:**\n{ticket.description}\n\n**Solusi Helpdesk:**\n{ticket.admin_response}"

    try:
        new_kb = KnowledgeBase(
            title=ticket.subject,
            content=kb_content,
            category=ticket.category,
            division=ticket.division,
        )

        db.add(new_kb)
        db.commit()
        db.refresh(new_kb)

        logger.success(f"Knowledge Base baru #{new_kb.id} berhasil dibuat dari Tiket #{ticket_id}")

        return {
            "message": "Artikel Knowledge Base berhasil dibuat dari tiket",
            "kb_id": new_kb.id,
            "data": new_kb
        }

    except Exception as e:
        logger.error(f"Gagal membuat KB dari tiket: {str(e)}")
        raise HTTPException(status_code=500, detail="Terjadi kesalahan server saat menyimpan Knowledge Base")
