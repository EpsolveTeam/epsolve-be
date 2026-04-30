from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from loguru import logger

from app.db.session import get_session
from app.models.chat_log import ChatLog
from app.models.user import User, UserRole
from app.core.dependencies import get_current_user, require_karyawan
from app.services.rag_service import RAGService

router = APIRouter()

class ChatMessageRequest(BaseModel):
    session_id: str
    user_id: Optional[UUID] = None
    user_query: str
    image_query_url: Optional[str] = None

class RAGResponse(BaseModel):
    answer: str
    sources: List[dict]

@router.post("/", status_code=status.HTTP_201_CREATED)
async def chat_with_bot(
    chat_in: ChatMessageRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_karyawan),
):
    """
    Endpoint untuk mengirim pesan ke chatbot.
    Menggunakan RAG (Retrieval-Augmented Generation) untuk menghasilkan jawaban.
    """
    logger.info(f"Menerima chat dari {current_user.email} | Session: {chat_in.session_id}")

    try:
        rag = RAGService(db=db)

        rag_result = await rag.query(
            query=chat_in.user_query,
            limit=5
        )

        answer = rag_result["answer"]
        sources = rag_result["sources"]

        new_chat_log = ChatLog(
            session_id=chat_in.session_id,
            user_id=chat_in.user_id if chat_in.user_id else current_user.id,
            user_query=chat_in.user_query,
            image_query_url=chat_in.image_query_url,
            bot_response=answer,
            is_resolved=True
        )
        db.add(new_chat_log)
        db.commit()
        db.refresh(new_chat_log)

        logger.success(f"Chat riwayat ID #{new_chat_log.id} berhasil disimpan dengan {len(sources)} sumber.")

        return {
            "message": "Pesan berhasil diproses",
            "data": {
                "chat_log": new_chat_log,
                "sources": sources
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Gagal memproses chat: {str(e)}")
        raise HTTPException(status_code=500, detail="Terjadi kesalahan pada server saat memproses chat")

@router.get("/history/{session_id}", response_model=List[ChatLog])
def get_chat_history(
    session_id: str,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_karyawan),
):
    """
    Endpoint untuk mengambil riwayat percakapan berdasarkan Session ID.
    Karyawan hanya bisa akses sesi miliknya sendiri; admin bisa akses semua.
    """
    logger.info(f"Mengambil riwayat chat untuk session_id: {session_id}")

    query = db.query(ChatLog).filter(ChatLog.session_id == session_id)

    if current_user.role != UserRole.ADMIN:
        query = query.filter(ChatLog.user_id == current_user.id)

    chat_history = query.order_by(ChatLog.created_at.asc()).all()

    if not chat_history:
        logger.warning(f"Riwayat chat tidak ditemukan untuk session_id: {session_id}")
        return []

    return chat_history

class ChatSessionItem(BaseModel):
    session_id: str
    title: str
    created_at: datetime
    
@router.get("/sessions", response_model=List[ChatSessionItem])
def get_chat_sessions(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user) 
):
    """
    Mengambil daftar riwayat sesi chat user untuk ditampilkan di Sidebar.
    Judul (title) diambil dari pertanyaan pertama user di sesi tersebut.
    """
    chats = db.query(ChatLog).filter(ChatLog.user_id == current_user.id).order_by(desc(ChatLog.created_at)).all()
    
    sessions_dict = {}
    
    for chat in chats:
        if chat.session_id not in sessions_dict:
            title = (chat.user_query[:30] + '...') if len(chat.user_query) > 30 else chat.user_query
            
            sessions_dict[chat.session_id] = {
                "session_id": chat.session_id,
                "title": title,
                "created_at": chat.created_at
            }
            
    result = list(sessions_dict.values())
    
    return result