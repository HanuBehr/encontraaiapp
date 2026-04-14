from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Enum as SAEnum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import ActivityAction
from app.models.base import Base, CreatedAtMixin


class ActivityLog(CreatedAtMixin, Base):
    __tablename__ = "activity_logs"
    __table_args__ = (
        Index("ix_activity_logs_org_lead_created", "organization_id", "lead_id", "created_at"),
        Index("ix_activity_logs_org_action_created", "organization_id", "action", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("leads.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer)
    action: Mapped[ActivityAction] = mapped_column(
        SAEnum(ActivityAction, native_enum=False),
        nullable=False,
        index=True,
    )
    actor: Mapped[str] = mapped_column(String(120), nullable=False, default="system")
    message: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    organization: Mapped["Organization | None"] = relationship("Organization", back_populates="activity_logs")
    lead: Mapped["Lead | None"] = relationship("Lead", back_populates="activity_logs")
