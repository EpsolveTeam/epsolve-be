from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class KnowledgeCreate(BaseModel):
    title: str
    content: str
    category: str
    division: str

class KnowledgeListResponse(BaseModel):
    id: int
    title: str
    category: str
    division: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class KnowledgeDetailResponse(BaseModel):
    id: int
    title: str
    content: str
    category: str
    division: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class KnowledgeResponse(BaseModel):
    id: int
    title: str
    content: str
    category: str
    division: str
    source_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class KnowledgeUpdate(BaseModel):
    content: str
