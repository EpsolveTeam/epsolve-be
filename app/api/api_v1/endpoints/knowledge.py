from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from loguru import logger

from app.db.session import get_session
from app.models.knowledge import KnowledgeBase
from app.core.dependencies import require_karyawan, require_admin
from app.models.user import User

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
    category: Optional[str] = None,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_karyawan),
):
    """
    Endpoint untuk READ semua data Knowledge Base.
    Bisa difilter berdasarkan kategori menggunakan query parameter (?category=...).
    """
    logger.info(f"User {current_user.email} mengambil daftar Knowledge Base.")
    
    query = db.query(KnowledgeBase)
    if category:
        query = query.filter(KnowledgeBase.category == category)
        
    results = query.all()
    return results

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