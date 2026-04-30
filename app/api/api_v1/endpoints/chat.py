from datetime import datetime
from uuid import UUID
import os
from fastapi import APIRouter, Depends, HTTPException, status, Form, File, UploadFile
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from loguru import logger

from app.db.session import get_session
from app.models.chat_log import ChatLog
from app.models.user import User, UserRole
from app.core.dependencies import get_current_user, require_karyawan
from app.services.rag_service import RAGService
from app.core.config import settings

# Supabase client for storage
from supabase import create_client, Client
supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

router = APIRouter()

class RAGResponse(BaseModel):
    answer: str
    sources: List[dict]

MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB

MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB

async def upload_image_to_supabase(image: UploadFile, user_id: UUID, session_id: str) -> str:
    """Upload image to Supabase Storage and return public URL."""
    # Read content
    content = await image.read()
    if not content:
        raise HTTPException(status_code=400, detail="Image file is empty")
    
    # Validate size (max 10 MB)
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Image file too large. Maximum size is {MAX_IMAGE_SIZE // (1024*1024)} MB"
        )

    # Determine file extension
    filename = image.filename or "image.jpg"
    ext = os.path.splitext(filename)[1] or ".jpg"
    # Unique path: {user_id}/{session_id}/{uuid4}{ext}
    # Ensure all parts are strings
    user_id_str = str(user_id)
    session_id_str = str(session_id)
    unique_name = str(UUID())
    storage_path = f"{user_id_str}/{session_id_str}/{unique_name}{ext}"

    try:
        # Upload to Supabase Storage (bucket: chat-images)
        supabase.storage.from_("chat-images").upload(
            path=storage_path,
            file=content,
            file_options={"content-type": image.content_type or "image/jpeg"}
        )

        # Get public URL (if bucket is public)
        public_url = supabase.storage.from_("chat-images").get_public_url(storage_path)
        return public_url
    except Exception as e:
        logger.error(f"Failed to upload image to Supabase Storage: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload image")

@router.post("/", status_code=status.HTTP_201_CREATED)
async def chat_with_bot(
    session_id: str = Form(...),
    user_query: str = Form(...),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_session),
    current_user: User = Depends(require_karyawan),
):
    """
    Endpoint untuk mengirim pesan ke chatbot.
    Menerima optional image upload (multipart/form-data).
    """
    logger.info(f"Menerima chat dari {current_user.email} | Session: {session_id}")

    try:
        # Process image upload if provided
        image_url = None
        if image:
            logger.info("Image detected, uploading to Supabase Storage...")
            image_url = await upload_image_to_supabase(image, current_user.id, session_id)
            logger.info(f"Image uploaded: {image_url}")

        # Initialize RAG service
        rag = RAGService(db=db)

        # Run RAG query (with image_url if available)
        rag_result = await rag.query(
            query=user_query,
            limit=5,
            image_url=image_url
        )

        answer = rag_result["answer"]
        sources = rag_result["sources"]

        # Save to ChatLog
        new_chat_log = ChatLog(
            session_id=session_id,
            user_id=current_user.id,
            user_query=user_query,
            image_query_url=image_url,
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