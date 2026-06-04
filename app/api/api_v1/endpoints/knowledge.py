from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from loguru import logger

from app.db.session import get_session
from app.models.knowledge import KnowledgeBase
from app.models.user import User
from app.core.dependencies import require_karyawan, require_admin
from app.services.embedding_service import get_embedding
from app.services.rag_service import invalidate_bm25_cache
from app.schemas.knowledge import KnowledgeCreate, KnowledgeResponse, KnowledgeUpdate, KnowledgeListResponse, KnowledgeDetailResponse

router = APIRouter()


def _get_kb_by_faq_or_404(db: Session, faq_id: str) -> KnowledgeBase:
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.faq_id == faq_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="Data Knowledge Base dengan faq_id tersebut tidak ditemukan")
    return kb


@router.post("/", response_model=KnowledgeResponse, status_code=status.HTTP_201_CREATED)
def create_knowledge(
    kb_in: KnowledgeCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """
    Endpoint untuk Admin menambahkan data Knowledge Base baru (Create).
    Embedding akan di-generate otomatis dari konten.
    """
    logger.info(f"Admin {current_user.email} menambahkan knowledge base baru: {kb_in.title} ({kb_in.category})")

    # Cek duplikasi faq_id jika disediakan
    if kb_in.faq_id:
        existing = db.query(KnowledgeBase).filter(KnowledgeBase.faq_id == kb_in.faq_id).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"faq_id '{kb_in.faq_id}' sudah digunakan oleh Knowledge Base ID #{existing.id}"
            )

    try:
        embedding = get_embedding(kb_in.content)

        new_kb = KnowledgeBase(
            title=kb_in.title,
            content=kb_in.content,
            category=kb_in.category,
            division=kb_in.division,
            faq_id=kb_in.faq_id,
            embedding=embedding
        )

        db.add(new_kb)
        db.commit()
        db.refresh(new_kb)

        invalidate_bm25_cache()

        logger.success(f"Knowledge Base ID #{new_kb.id} (faq_id={new_kb.faq_id}) berhasil disimpan dengan embedding.")
        return new_kb

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Gagal menyimpan knowledge base: {str(e)}")
        raise HTTPException(status_code=500, detail="Terjadi kesalahan pada server")


@router.get("/", response_model=List[KnowledgeListResponse])
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
    
    return query.order_by(KnowledgeBase.updated_at.desc()).all()


@router.get("/summary/stats")
def get_knowledge_summary(
    db: Session = Depends(get_session),
    current_user: User = Depends(require_karyawan)
):
    """
    Mengambil statistik total pertanyaan (Knowledge Base) 
    dan rincian jumlah pertanyaan per kategori.
    """
    logger.info(f"User {current_user.email} mengakses statistik Knowledge Base.")

    try:
        total_pertanyaan = db.query(KnowledgeBase).count()

        category_counts = db.query(
            KnowledgeBase.category,
            func.count(KnowledgeBase.id).label("count")
        ).group_by(KnowledgeBase.category).all()

        detail_kategori = {cat: count for cat, count in category_counts if cat}

        return {
            "total_pertanyaan": total_pertanyaan,
            "kategori_detail": detail_kategori
        }

    except Exception as e:
        logger.error(f"Gagal mengambil statistik Knowledge Base: {str(e)}")
        raise HTTPException(status_code=500, detail="Terjadi kesalahan saat menghitung statistik")


@router.get("/by-faq/{faq_id}", response_model=KnowledgeDetailResponse)
def get_knowledge_by_faq_id(
    faq_id: str,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_karyawan),
):
    """
    Endpoint untuk melihat detail Knowledge Base berdasarkan faq_id.
    """
    kb_data = _get_kb_by_faq_or_404(db, faq_id)
    return kb_data


@router.put("/by-faq/{faq_id}", response_model=KnowledgeResponse)
def update_knowledge_by_faq_id(
    faq_id: str,
    kb_in: KnowledgeUpdate,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """
    Endpoint untuk UPDATE data Knowledge Base berdasarkan faq_id.
    """
    kb_data = _get_kb_by_faq_or_404(db, faq_id)

    if kb_in.content != kb_data.content:
        kb_data.content = kb_in.content
        try:
            kb_data.embedding = get_embedding(kb_in.content)
        except Exception as e:
            logger.error(f"Failed to regenerate embedding: {e}")
            raise HTTPException(status_code=500, detail="Gagal mengupdate embedding AI")

    # Update faq_id jika disediakan
    if kb_in.faq_id is not None and kb_in.faq_id != kb_data.faq_id:
        existing = db.query(KnowledgeBase).filter(
            KnowledgeBase.faq_id == kb_in.faq_id,
            KnowledgeBase.id != kb_data.id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"faq_id '{kb_in.faq_id}' sudah digunakan"
            )
        kb_data.faq_id = kb_in.faq_id

    db.commit()
    db.refresh(kb_data)

    invalidate_bm25_cache()

    logger.info(f"Knowledge Base faq_id={faq_id} berhasil diperbarui oleh {current_user.email}.")
    return kb_data


@router.delete("/by-faq/{faq_id}")
def delete_knowledge_by_faq_id(
    faq_id: str,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """
    Endpoint untuk DELETE Knowledge Base berdasarkan faq_id.
    """
    kb_data = _get_kb_by_faq_or_404(db, faq_id)

    db.delete(kb_data)
    db.commit()

    invalidate_bm25_cache()

    logger.success(f"Knowledge Base faq_id={faq_id} berhasil dihapus oleh {current_user.email}.")

    return {"message": f"Knowledge Base faq_id={faq_id} berhasil dihapus"}