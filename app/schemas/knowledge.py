from pydantic import BaseModel
from typing import Optional

class KnowledgeCreate(BaseModel):
    title: str
    content: str
    category: str

class KnowledgeResponse(BaseModel):
    id: int
    title: str
    content: str
    category: str
    source_url: Optional[str] = None

    class Config:
        from_attributes = True

class KnowledgeUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
