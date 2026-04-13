from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.app_setting import AppSetting


class SettingsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_settings(self) -> list[AppSetting]:
        query = select(AppSetting).order_by(AppSetting.key.asc())
        return self.db.execute(query).scalars().all()
