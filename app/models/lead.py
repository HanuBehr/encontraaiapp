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
        Index("ix_leads_org_city_state", "organization_id", "city", "state"),
        Index("ix_leads_org_status_city", "organization_id", "status", "city"),
        Index("ix_leads_org_google_place_id", "organization_id", "google_place_id", unique=True),
        Index("ix_leads_org_sales_region", "organization_id", "sales_region_id"),
        Index("ix_leads_org_market_segment", "organization_id", "market_segment_id"),
        Index("ix_leads_org_market_subsegment", "organization_id", "market_subsegment_id"),
        Index("ix_leads_org_assigned_sales_rep", "organization_id", "assigned_sales_rep_id"),
        Index("ix_leads_org_assignment_rule", "organization_id", "assignment_rule_id"),
        Index("ix_leads_org_company_size_fit", "organization_id", "company_size_fit"),
        Index("ix_leads_org_trade_type", "organization_id", "trade_type"),
        Index("ix_leads_org_is_blocked", "organization_id", "is_blocked"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
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
    google_place_id: Mapped[str | None] = mapped_column(String(128), index=True)
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
    sales_region_id: Mapped[int | None] = mapped_column(ForeignKey("sales_regions.id"), index=True)
    market_segment_id: Mapped[int | None] = mapped_column(ForeignKey("market_segments.id"), index=True)
    market_subsegment_id: Mapped[int | None] = mapped_column(ForeignKey("market_subsegments.id"), index=True)
    assigned_sales_rep_id: Mapped[int | None] = mapped_column(ForeignKey("sales_reps.id"), index=True)
    assignment_rule_id: Mapped[int | None] = mapped_column(ForeignKey("assignment_rules.id"), index=True)
    assignment_explanation: Mapped[str | None] = mapped_column(Text)
    assignment_metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    company_size_fit: Mapped[str] = mapped_column(String(40), default="unknown", nullable=False, index=True)
    company_size_fit_explanation: Mapped[str | None] = mapped_column(Text)
    company_size_fit_metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    trade_type: Mapped[str] = mapped_column(String(40), default="unknown", nullable=False, index=True)
    trade_type_explanation: Mapped[str | None] = mapped_column(Text)
    trade_type_metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    quality_classified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    blocked_reason: Mapped[str | None] = mapped_column(Text)
    blocked_rule_id: Mapped[int | None] = mapped_column(ForeignKey("lead_exclusion_rules.id"), index=True)
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    organization: Mapped["Organization | None"] = relationship("Organization", back_populates="leads")
    sales_region: Mapped["SalesRegion | None"] = relationship("SalesRegion", back_populates="assigned_leads")
    market_segment: Mapped["MarketSegment | None"] = relationship("MarketSegment", back_populates="classified_leads")
    market_subsegment: Mapped["MarketSubsegment | None"] = relationship(
        "MarketSubsegment",
        back_populates="classified_leads",
    )
    assigned_sales_rep: Mapped["SalesRep | None"] = relationship("SalesRep", back_populates="assigned_leads")
    assignment_rule: Mapped["AssignmentRule | None"] = relationship("AssignmentRule", back_populates="assigned_leads")
    blocked_rule: Mapped["LeadExclusionRule | None"] = relationship("LeadExclusionRule", back_populates="blocked_leads")
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
