from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from loguru import logger

from app.db.session import get_session
from app.models.chat_log import ChatLog
from sqlalchemy import desc
from app.core.dependencies import get_current_user
from app.models.user import User
# from app.models.knowledge import KnowledgeBase # [TODO] Model untuk knowledge base (pgvector)

router = APIRouter()

class ChatMessageRequest(BaseModel):
    session_id: str
    user_id: Optional[int] = None
    user_query: str
    image_query_url: Optional[str] = None

@router.post("/", status_code=status.HTTP_201_CREATED)
def chat_with_bot(chat_in: ChatMessageRequest, db: Session = Depends(get_session)):
    """
    Endpoint untuk mengirim pesan ke chatbot
    """
    logger.info(f"Menerima chat dari User ID {chat_in.user_id} | Session: {chat_in.session_id}")
    
    try:
        # =====================================================================
        # [TODO] INTEGRASI AI / RAG
        # =====================================================================
        
        # 1. Preprocessing & Intent Detection
        # user_intent = nlp_service.detect_intent(chat_in.user_query)
        
        # 2. Generate Embedding dari User Query menggunakan OpenAI
        # query_embedding = openai_service.get_embedding(chat_in.user_query)
        
        # 3. Semantic Search ke Database (pgvector)
        # relevant_docs = db.query(KnowledgeBase).order_by(
        #     KnowledgeBase.embedding.cosine_distance(query_embedding)
        # ).limit(3).all()
        
        # 4. Generate Response dengan LLM (OpenAI) berdasarkan konteks dokumen
        # context = "\n".join([doc.content for doc in relevant_docs])
        # bot_response_text = openai_service.generate_answer(chat_in.user_query, context)
        
        # 5. Simpan ke tabel ChatLog
        # new_chat_log = ChatLog(
        #     session_id=chat_in.session_id,
        #     user_id=chat_in.user_id,
        #     user_query=chat_in.user_query,
        #     image_query_url=chat_in.image_query_url,
        #     bot_response=bot_response_text,
        #     is_resolved=True
        # )
        # db.add(new_chat_log)
        # db.commit()
        # db.refresh(new_chat_log)
        # 
        # logger.success(f"Chat riwayat ID #{new_chat_log.id} berhasil disimpan.")
        # return {"message": "Pesan berhasil diproses", "data": new_chat_log}
        
        # =====================================================================

        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Gagal memproses chat: {str(e)}")
        raise HTTPException(status_code=500, detail="Terjadi kesalahan pada server saat memproses chat")

@router.get("/history/{session_id}", response_model=List[ChatLog])
def get_chat_history(session_id: str, db: Session = Depends(get_session)):
    """
    Endpoint untuk mengambil riwayat percakapan berdasarkan Session ID.
    """
    logger.info(f"Mengambil riwayat chat untuk session_id: {session_id}")
    
    chat_history = db.query(ChatLog).filter(ChatLog.session_id == session_id).order_by(ChatLog.created_at.asc()).all()
    
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
    current_user: User = Depends(get_current_user) # Pakai user yang sedang login
):
    """
    Mengambil daftar riwayat sesi chat user untuk ditampilkan di Sidebar.
    Judul (title) diambil dari pertanyaan pertama user di sesi tersebut.
    """
    # Ambil semua chat milik user ini, urutkan dari yang terbaru
    chats = db.query(ChatLog).filter(ChatLog.user_id == current_user.id).order_by(desc(ChatLog.created_at)).all()
    
    sessions_dict = {}
    
    # Grouping berdasarkan session_id
    for chat in chats:
        if chat.session_id not in sessions_dict:
            title = (chat.user_query[:30] + '...') if len(chat.user_query) > 30 else chat.user_query
            
            sessions_dict[chat.session_id] = {
                "session_id": chat.session_id,
                "title": title,
                "created_at": chat.created_at
            }
            
    # Convert dictionary ke list
    result = list(sessions_dict.values())
    
    return result