from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db


def get_db_session() -> Generator[Session, None, None]:
    yield from get_db()


def get_app_settings() -> Settings:
    return get_settings()
