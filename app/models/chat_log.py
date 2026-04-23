from uuid import UUID
from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional

class ChatLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str
    user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    user_query: str
    image_query_url: Optional[str] = None
    bot_response: str
    is_resolved: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)