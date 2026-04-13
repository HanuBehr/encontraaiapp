from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.enums import DraftStatus, OutreachChannel, TemplateKey


class TemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int
    key: TemplateKey
    channel: OutreachChannel
    name: str
    subject_template: str | None = None
    body_template: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int
    lead_id: int
    template_id: int | None = None
    channel: OutreachChannel
    draft_type: TemplateKey
    subject: str | None = None
    body: str
    personalization: dict[str, Any] = Field(default_factory=dict)
    status: DraftStatus
    approved_by: str | None = None
    approved_at: datetime | None = None
    rejected_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class DraftPreviewRequest(BaseModel):
    template_key: TemplateKey


class DraftGenerateRequest(BaseModel):
    template_key: TemplateKey


class DraftPreviewResponse(BaseModel):
    lead_id: int
    template_key: TemplateKey
    channel: OutreachChannel
    subject: str | None = None
    body: str
    personalization: dict[str, Any] = Field(default_factory=dict)


class DraftStatusUpdateRequest(BaseModel):
    status: DraftStatus
    rejected_reason: str | None = None
