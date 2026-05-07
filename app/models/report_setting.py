from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone

class ReportSetting(SQLModel, table=True):
    __tablename__ = "report_setting"

    id: Optional[int] = Field(default=None, primary_key=True)
    recipient_email: str = Field(unique=True, index=True)
    period: str = Field(...)
    last_sent_at: Optional[datetime] = Field(default=None)
    is_active: bool = Field(default=True)
