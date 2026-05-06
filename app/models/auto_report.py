from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional


class AutoReportSetting(SQLModel, table=True):
    __tablename__ = "auto_report_setting"

    id: int = Field(default=1, primary_key=True)
    email: str = Field(default="")
    period: str = Field(default="off")   # off | 1w | 1m | 3m
    is_active: bool = Field(default=False)
    updated_at: Optional[datetime] = Field(default=None)
