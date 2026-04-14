from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AssignmentRule(TimestampMixin, Base):
    __tablename__ = "assignment_rules"
    __table_args__ = (
        Index("ix_assignment_rules_org_priority", "organization_id", "priority"),
        Index("ix_assignment_rules_org_active", "organization_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    sales_region_id: Mapped[int | None] = mapped_column(ForeignKey("sales_regions.id"), index=True)
    market_segment_id: Mapped[int | None] = mapped_column(ForeignKey("market_segments.id"), index=True)
    market_subsegment_id: Mapped[int | None] = mapped_column(ForeignKey("market_subsegments.id"), index=True)
    sales_rep_id: Mapped[int] = mapped_column(ForeignKey("sales_reps.id"), nullable=False, index=True)
    conditions_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="assignment_rules")
    sales_region: Mapped["SalesRegion | None"] = relationship("SalesRegion", back_populates="assignment_rules")
    market_segment: Mapped["MarketSegment | None"] = relationship("MarketSegment", back_populates="assignment_rules")
    market_subsegment: Mapped["MarketSubsegment | None"] = relationship(
        "MarketSubsegment",
        back_populates="assignment_rules",
    )
    sales_rep: Mapped["SalesRep"] = relationship("SalesRep", back_populates="assignment_rules")
    assigned_leads: Mapped[list["Lead"]] = relationship("Lead", back_populates="assignment_rule")
