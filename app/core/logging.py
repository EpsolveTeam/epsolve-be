import sys
from loguru import logger
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "app_runtime.log"

def setup_logging():
    logger.remove()

    logger.add(
        sys.stdout,
        enqueue=True,
        backtrace=True,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )

    logger.add(
        str(LOG_FILE),
        rotation="10 MB",
        retention="10 days",
        level="DEBUG",
        compression="zip",
        enqueue=True,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
    )

    return logger