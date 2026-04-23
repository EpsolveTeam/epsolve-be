import uuid
from uuid import UUID
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import DateTime, String, func
from enum import Enum
from datetime import datetime
from typing import Optional


class UserRole(str, Enum):
    KARYAWAN = "karyawan"
    HELPDESK = "helpdesk"
    ADMIN = "admin"


class User(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(unique=True, index=True)
    full_name: str
    hashed_password: str
    role: UserRole = Field(default=UserRole.KARYAWAN, sa_column=Column(String, nullable=False))
    is_active: bool = Field(default=True)
    refresh_token_hash: Optional[str] = Field(default=None, nullable=True)
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime, server_default=func.now(), nullable=False),
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False),
    )
