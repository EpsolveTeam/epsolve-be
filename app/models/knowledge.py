from sqlmodel import SQLModel, Field, Column
from pgvector.sqlalchemy import Vector
from typing import List, Optional

class KnowledgeBase(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(default="Untitled")
    content: str
    category: str = Field(default="General")
    # Kolom vektor dengan dimensi 1536 (standar OpenAI text-embedding-3-small)
    embedding: List[float] = Field(sa_column=Column(Vector(1536)))