import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel
from app.core.config import settings
from app.api.api_v1.api import api_router
from app.core.logging import setup_logging
from app.db.session import engine

# Import semua model agar SQLModel.metadata mengetahui semua tabel
import app.models.user
import app.models.ticket
import app.models.chat_log
import app.models.knowledge
import app.models.auto_report

setup_logging()

env_state = os.getenv("ENV_STATE", "")
current_root_path = f"/{env_state}" if env_state in ["dev", "prod"] else ""

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API Epsolve",
    version="1.0.0",
    root_path=current_root_path 
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)

@app.get("/")
def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API",
        "status": "online",
        "environment": env_state if env_state else "local",
        "docs": f"{current_root_path}/docs"
    }