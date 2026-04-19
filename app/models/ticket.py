from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional

class Ticket(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    user_email: str
    subject: str
    description: str
    category: str = Field(index=True) 
    image_url: Optional[str] = None
    status: str = Field(default="open")
    created_at: datetime = Field(default_factory=datetime.utcnow)