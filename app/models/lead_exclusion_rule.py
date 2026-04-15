from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class LeadExclusionRule(TimestampMixin, Base):
    __tablename__ = "lead_exclusion_rules"
    __table_args__ = (
        Index("ix_lead_exclusion_rules_org_active_type", "organization_id", "is_active", "rule_type"),
        Index("ix_lead_exclusion_rules_org_normalized_pattern", "organization_id", "normalized_pattern"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    rule_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    pattern: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_pattern: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="lead_exclusion_rules")
    blocked_leads: Mapped[list["Lead"]] = relationship("Lead", back_populates="blocked_rule")
