from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.api_v1.api import api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API Epson Smart Helpdesk",
    version="1.0.0"
)

# Konfigurasi CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Menghubungkan semua rute API
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API",
        "status": "online",
        "docs": "/docs"
    }