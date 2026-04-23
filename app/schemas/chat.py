from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    session_id: str
    bot_response: str
    is_resolved: bool


class ChatLogResponse(BaseModel):
    id: int
    session_id: str
    user_id: Optional[UUID]
    user_query: str
    image_query_url: Optional[str]
    bot_response: str
    is_resolved: bool
    created_at: datetime

    model_config = {"from_attributes": True}