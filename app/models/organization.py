from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(160))
    timezone: Mapped[str] = mapped_column(String(80), default="America/Sao_Paulo", nullable=False)
    default_locale: Mapped[str] = mapped_column(String(16), default="pt-BR", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    branding_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    terminology_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    leads: Mapped[list["Lead"]] = relationship("Lead", back_populates="organization")
    lead_contacts: Mapped[list["LeadContact"]] = relationship("LeadContact", back_populates="organization")
    lead_enrichment_records: Mapped[list["LeadEnrichmentRecord"]] = relationship(
        "LeadEnrichmentRecord",
        back_populates="organization",
    )
    activity_logs: Mapped[list["ActivityLog"]] = relationship("ActivityLog", back_populates="organization")
    sales_reps: Mapped[list["SalesRep"]] = relationship("SalesRep", back_populates="organization")
    sales_regions: Mapped[list["SalesRegion"]] = relationship("SalesRegion", back_populates="organization")
    market_segments: Mapped[list["MarketSegment"]] = relationship("MarketSegment", back_populates="organization")
    assignment_rules: Mapped[list["AssignmentRule"]] = relationship("AssignmentRule", back_populates="organization")
