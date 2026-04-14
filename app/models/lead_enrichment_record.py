from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, utcnow


class LeadEnrichmentRecord(CreatedAtMixin, Base):
    __tablename__ = "lead_enrichment_records"
    __table_args__ = (
        Index("ix_lead_enrichment_lead_fetched", "lead_id", "fetched_at"),
        Index("ix_lead_enrichment_org_lead_fetched", "organization_id", "lead_id", "fetched_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), nullable=False, index=True)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    page_type: Mapped[str | None] = mapped_column(String(100))
    http_status: Mapped[int | None] = mapped_column(Integer)
    robots_allowed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    extracted_fields: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    confidence_scores: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    inferred_material_signals: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    organization: Mapped["Organization | None"] = relationship(
        "Organization",
        back_populates="lead_enrichment_records",
    )
    lead: Mapped["Lead"] = relationship("Lead", back_populates="enrichments")
