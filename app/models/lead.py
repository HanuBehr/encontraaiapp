from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import LeadSourceType, LeadStatus
from app.models.base import Base, TimestampMixin


class Lead(TimestampMixin, Base):
    __tablename__ = "leads"
    __table_args__ = (
        Index("ix_leads_city_state", "city", "state"),
        Index("ix_leads_status_city", "status", "city"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_business_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(255))
    lead_source_type: Mapped[LeadSourceType] = mapped_column(
        SAEnum(LeadSourceType, native_enum=False),
        nullable=False,
        default=LeadSourceType.GOOGLE_PLACES,
        index=True,
    )
    address: Mapped[str | None] = mapped_column(String(255))
    neighborhood: Mapped[str | None] = mapped_column(String(120))
    city: Mapped[str | None] = mapped_column(String(120), index=True)
    state: Mapped[str | None] = mapped_column(String(80))
    postal_code: Mapped[str | None] = mapped_column(String(32))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    website: Mapped[str | None] = mapped_column(String(255))
    domain: Mapped[str | None] = mapped_column(String(255), index=True)
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32))
    whatsapp: Mapped[str | None] = mapped_column(String(32))
    instagram: Mapped[str | None] = mapped_column(String(255))
    google_maps_url: Mapped[str | None] = mapped_column(String(500))
    google_place_id: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    source_provider: Mapped[str | None] = mapped_column(String(100))
    source_url: Mapped[str | None] = mapped_column(String(500))
    material_profile: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    lead_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[LeadStatus] = mapped_column(
        SAEnum(LeadStatus, native_enum=False),
        nullable=False,
        default=LeadStatus.NEW,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    follow_up_date: Mapped[date | None] = mapped_column(Date)
    owner: Mapped[str | None] = mapped_column(String(120))
    approved_for_send: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    do_not_contact: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    duplicate_of_lead_id: Mapped[int | None] = mapped_column(ForeignKey("leads.id", ondelete="SET NULL"))
    duplicate_reason: Mapped[str | None] = mapped_column(Text)
    last_contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    duplicate_of: Mapped["Lead | None"] = relationship(
        "Lead",
        remote_side=lambda: [Lead.id],
        back_populates="duplicates",
    )
    duplicates: Mapped[list["Lead"]] = relationship("Lead", back_populates="duplicate_of")
    raw_discovery_records: Mapped[list["RawDiscoveryRecord"]] = relationship(
        "RawDiscoveryRecord",
        back_populates="lead",
    )
    contacts: Mapped[list["LeadContact"]] = relationship("LeadContact", back_populates="lead")
    enrichments: Mapped[list["LeadEnrichmentRecord"]] = relationship(
        "LeadEnrichmentRecord",
        back_populates="lead",
    )
    outreach_drafts: Mapped[list["OutreachDraft"]] = relationship(
        "OutreachDraft",
        back_populates="lead",
    )
    outreach_messages: Mapped[list["OutreachMessage"]] = relationship(
        "OutreachMessage",
        back_populates="lead",
    )
    activity_logs: Mapped[list["ActivityLog"]] = relationship("ActivityLog", back_populates="lead")
