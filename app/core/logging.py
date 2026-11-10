"""Loguru setup."""
import sys

from loguru import logger

from app.core.config import settings


def setup_logging() -> None:
    logger.remove()
    logger.add(sys.stdout, level=settings.LOG_LEVEL, format="{time:HH:mm:ss} | {level} | {extra[name]} - {message}")


def get_logger(name: str):
    return logger.bind(name=name)


logger.configure(extra={"name": "app"})
