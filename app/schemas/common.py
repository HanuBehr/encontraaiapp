from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ORMBaseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class HealthResponse(BaseModel):
    status: str
    app_env: str
    database_ok: bool
    timestamp: datetime


class MessageResponse(BaseModel):
    message: str
