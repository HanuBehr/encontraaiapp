from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import DraftStatus, MessageStatus, OutreachChannel, TemplateKey
from app.models.base import Base, TimestampMixin


class OutreachTemplate(TimestampMixin, Base):
    __tablename__ = "outreach_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[TemplateKey] = mapped_column(
        SAEnum(TemplateKey, native_enum=False),
        unique=True,
        nullable=False,
        index=True,
    )
    channel: Mapped[OutreachChannel] = mapped_column(
        SAEnum(OutreachChannel, native_enum=False),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    subject_template: Mapped[str | None] = mapped_column(String(255))
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    drafts: Mapped[list["OutreachDraft"]] = relationship("OutreachDraft", back_populates="template")


class OutreachDraft(TimestampMixin, Base):
    __tablename__ = "outreach_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), nullable=False, index=True)
    template_id: Mapped[int | None] = mapped_column(ForeignKey("outreach_templates.id"), index=True)
    channel: Mapped[OutreachChannel] = mapped_column(
        SAEnum(OutreachChannel, native_enum=False),
        nullable=False,
        index=True,
    )
    draft_type: Mapped[TemplateKey] = mapped_column(
        SAEnum(TemplateKey, native_enum=False),
        nullable=False,
        index=True,
    )
    subject: Mapped[str | None] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    personalization: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[DraftStatus] = mapped_column(
        SAEnum(DraftStatus, native_enum=False),
        nullable=False,
        default=DraftStatus.PENDING_REVIEW,
        index=True,
    )
    approved_by: Mapped[str | None] = mapped_column(String(120))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_reason: Mapped[str | None] = mapped_column(Text)

    lead: Mapped["Lead"] = relationship("Lead", back_populates="outreach_drafts")
    template: Mapped["OutreachTemplate | None"] = relationship("OutreachTemplate", back_populates="drafts")
    messages: Mapped[list["OutreachMessage"]] = relationship("OutreachMessage", back_populates="draft")


class OutreachMessage(TimestampMixin, Base):
    __tablename__ = "outreach_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), nullable=False, index=True)
    draft_id: Mapped[int | None] = mapped_column(ForeignKey("outreach_drafts.id"), index=True)
    channel: Mapped[OutreachChannel] = mapped_column(
        SAEnum(OutreachChannel, native_enum=False),
        nullable=False,
        index=True,
    )
    provider: Mapped[str | None] = mapped_column(String(100))
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[MessageStatus] = mapped_column(
        SAEnum(MessageStatus, native_enum=False),
        nullable=False,
        default=MessageStatus.QUEUED,
        index=True,
    )
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    response_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    lead: Mapped["Lead"] = relationship("Lead", back_populates="outreach_messages")
    draft: Mapped["OutreachDraft | None"] = relationship("OutreachDraft", back_populates="messages")
