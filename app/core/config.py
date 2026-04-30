import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

ENV_STATE = os.getenv("ENV_STATE", "dev")

class Settings(BaseSettings):
    PROJECT_NAME: str = "Epsolve"
    DATABASE_URL: str
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str
    GOOGLE_API_KEY: str

    BREVO_API_KEY: str
    BREVO_SENDER_EMAIL: str

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 6        # 6 jam 
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7               # 7 hari

    model_config = SettingsConfigDict(
        env_file=f".env.{ENV_STATE}",
        extra="ignore"
    )

settings = Settings()
print(f"--- {settings.PROJECT_NAME} is running in {ENV_STATE.upper()} mode ---")