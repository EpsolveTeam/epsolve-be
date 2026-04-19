import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

ENV_STATE = os.getenv("ENV_STATE", "dev")

class Settings(BaseSettings):
    PROJECT_NAME: str = "Epsolve" 
    DATABASE_URL: str 
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str
    OPENAI_API_KEY: str
    RESEND_API_KEY: str 
    
    MAIL_FROM: str = "onboarding@resend.dev"
    MAIL_TO: str 

    model_config = SettingsConfigDict(
        env_file=f".env.{ENV_STATE}",
        extra="ignore"
    )

settings = Settings()
print(f"--- {settings.PROJECT_NAME} is running in {ENV_STATE.upper()} mode ---")