from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import ActivityAction
from app.models.base import Base, CreatedAtMixin


class ActivityLog(CreatedAtMixin, Base):
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
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

    lead: Mapped["Lead | None"] = relationship("Lead", back_populates="activity_logs")
