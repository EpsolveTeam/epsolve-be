from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Epson Smart Helpdesk" 
    
    DATABASE_URL: str 
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str
    OPENAI_API_KEY: str
    RESEND_API_KEY: str 

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

settings = Settings()