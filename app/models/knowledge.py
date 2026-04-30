from sqlmodel import SQLModel, Field, Column
from sqlalchemy import DateTime, func, String, Text
from pgvector.sqlalchemy import Vector
from typing import List, Optional
from datetime import datetime

class KnowledgeBase(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(default="Untitled")
    content: str = Field(sa_column=Column(Text))
    category: str = Field(default="General", sa_column=Column(String(100)))
    division: Optional[str] = Field(default=None, sa_column=Column(String(100)))
    source_url: Optional[str] = Field(default=None, sa_column=Column(Text))
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime, server_default=func.now(), nullable=False),
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False),
    )
    embedding: List[float] = Field(sa_column=Column(Vector(384)))