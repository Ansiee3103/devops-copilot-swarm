import sys
import os
from loguru import logger

logger.remove()

logger.add(
    sys.stdout,
    format = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
             "<level>{level: <8}</level> | "
             "<cyan>{name}</cyan>:<cyan>{line}</cyan> | "
             "<level>{message}</level>",
    level     = "INFO",
    colorize  = True
)

os.makedirs("logs", exist_ok=True)

logger.add(
    "logs/app.log",
    format    = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{line} | {message}",
    level     = "DEBUG",
    rotation  = "10 MB",
    retention = "30 days",
    compression = "zip"
)

logger.add(
    "logs/errors.log",
    format    = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{line} | {message}",
    level     = "ERROR",
    rotation  = "10 MB",
    retention = "30 days"
)

def get_logger(name: str):
    return logger.bind(name=name)