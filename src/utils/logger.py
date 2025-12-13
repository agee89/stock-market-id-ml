import sys
from loguru import logger
from src.utils.config import get_settings

settings = get_settings()

# Configure logger
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=settings.LOG_LEVEL,
)
logger.add("logs/app.log", rotation="500 MB", level="DEBUG")

def get_logger():
    return logger
