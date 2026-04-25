from sqlmodel import SQLModel, Field, Column
from sqlalchemy import DateTime, func
from pgvector.sqlalchemy import Vector
from typing import List, Optional
from datetime import datetime

class KnowledgeBase(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(default="Untitled")
    content: str
    category: str = Field(default="General")
    product_type: Optional[str] = Field(default=None)
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime, server_default=func.now(), nullable=False),
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False),
    )
    # Kolom vektor dengan dimensi 1536 (standar OpenAI text-embedding-3-small)
    embedding: List[float] = Field(sa_column=Column(Vector(1536)))