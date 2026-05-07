from uuid import UUID
from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional

class Ticket(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    name: str
    user_email: str
    description: str
    category: str = Field(index=True) 
    division: Optional[str] = Field(default=None) 
    admin_response: Optional[str] = Field(default=None)
    image_url: Optional[str] = None
    status: str = Field(default="open")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)