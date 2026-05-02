from fastapi import APIRouter
from app.api.api_v1.endpoints import auth, tickets, chat, knowledge, analytics, options

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(options.router, prefix="/options", tags=["options"])
api_router.include_router(tickets.router, prefix="/tickets", tags=["tickets"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge base"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics & dashboard"])
