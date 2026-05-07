import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.api_v1.api import api_router
from app.core.logging import setup_logging
from app.core.scheduler import scheduler
from loguru import logger

setup_logging()

env_state = os.getenv("ENV_STATE", "")
current_root_path = f"/{env_state}" if env_state in ["dev", "prod"] else ""

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API Epsolve",
    version="1.0.0",
    root_path=current_root_path,
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
def start_scheduler():
    scheduler.start()
    logger.info("🤖 Background Scheduler Started!")


@app.on_event("shutdown")
def stop_scheduler():
    scheduler.shutdown()


@app.get("/")
def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API",
        "status": "online",
        "environment": env_state if env_state else "local",
        "docs": f"{current_root_path}/docs",
    }

