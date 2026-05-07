from pydantic import BaseModel, EmailStr


class ReportSettingInput(BaseModel):
    recipient_email: EmailStr
    period: str  # "1w", "1m", "3m"

