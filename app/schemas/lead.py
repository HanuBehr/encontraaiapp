from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.enums import ActivityAction, CompanySizeFit, ContactType, LeadSourceType, LeadStatus, TradeType
from app.schemas.common import ORMBaseModel


class SalesRegionRead(ORMBaseModel):
    id: int
    name: str
    region_type: str
    state: str | None = None
    code: str | None = None


class MarketSegmentRead(ORMBaseModel):
    id: int
    key: str
    name: str


class MarketSubsegmentRead(ORMBaseModel):
    id: int
    key: str
    name: str


class SalesRepRead(ORMBaseModel):
    id: int
    name: str
    email: str | None = None


class AssignmentRuleRead(ORMBaseModel):
    id: int
    name: str
    priority: int


class LeadSummary(ORMBaseModel):
    id: int
    business_name: str
    normalized_business_name: str
    category: str | None = None
    neighborhood: str | None = None
    city: str | None = None
    state: str | None = None
    email: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    website: str | None = None
    lead_score: int
    status: LeadStatus
    lead_source_type: LeadSourceType
    do_not_contact: bool
    approved_for_send: bool
    last_enriched_at: datetime | None = None
    last_contacted_at: datetime | None = None
    follow_up_date: date | None = None
    is_duplicate: bool
    duplicate_of_lead_id: int | None = None
    duplicate_reason: str | None = None
    sales_region_id: int | None = None
    market_segment_id: int | None = None
    market_subsegment_id: int | None = None
    assigned_sales_rep_id: int | None = None
    assignment_rule_id: int | None = None
    assigned_at: datetime | None = None
    company_size_fit: CompanySizeFit = CompanySizeFit.UNKNOWN
    company_size_fit_explanation: str | None = None
    trade_type: TradeType = TradeType.UNKNOWN
    trade_type_explanation: str | None = None
    quality_classified_at: datetime | None = None
    sales_region: SalesRegionRead | None = None
    market_segment: MarketSegmentRead | None = None
    market_subsegment: MarketSubsegmentRead | None = None
    assigned_sales_rep: SalesRepRead | None = None
    assignment_rule: AssignmentRuleRead | None = None
    created_at: datetime
    updated_at: datetime


class LeadContactRead(ORMBaseModel):
    id: int
    contact_type: ContactType
    raw_value: str
    normalized_value: str | None = None
    label: str | None = None
    source_url: str | None = None
    source_kind: str | None = None
    source_record_type: str | None = None
    source_record_id: int | None = None
    confidence: float
    is_primary: bool
    note: str | None = None
    created_at: datetime
    updated_at: datetime


class LeadEnrichmentRecordRead(ORMBaseModel):
    id: int
    source_url: str
    page_type: str | None = None
    http_status: int | None = None
    robots_allowed: bool
    extracted_fields: dict[str, Any]
    confidence_scores: dict[str, Any]
    inferred_material_signals: dict[str, Any]
    note: str | None = None
    fetched_at: datetime
    created_at: datetime


class ActivityLogRead(ORMBaseModel):
    id: int
    entity_type: str
    entity_id: int | None = None
    action: ActivityAction
    actor: str
    message: str | None = None
    metadata_json: dict[str, Any]
    created_at: datetime


class LeadDetail(LeadSummary):
    address: str | None = None
    postal_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    domain: str | None = None
    instagram: str | None = None
    google_maps_url: str | None = None
    google_place_id: str | None = None
    source_provider: str | None = None
    source_url: str | None = None
    material_profile: dict[str, Any] = Field(default_factory=dict)
    score_breakdown: dict[str, Any] = Field(default_factory=dict)
    assignment_explanation: str | None = None
    assignment_metadata_json: dict[str, Any] = Field(default_factory=dict)
    company_size_fit_metadata_json: dict[str, Any] = Field(default_factory=dict)
    trade_type_metadata_json: dict[str, Any] = Field(default_factory=dict)
    sales_region: SalesRegionRead | None = None
    market_segment: MarketSegmentRead | None = None
    market_subsegment: MarketSubsegmentRead | None = None
    assigned_sales_rep: SalesRepRead | None = None
    assignment_rule: AssignmentRuleRead | None = None
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    owner: str | None = None
    contacts: list[LeadContactRead] = Field(default_factory=list)
    enrichments: list[LeadEnrichmentRecordRead] = Field(default_factory=list)
    activity_logs: list[ActivityLogRead] = Field(default_factory=list)


class LeadListFilters(BaseModel):
    city: str | None = None
    status: LeadStatus | None = None
    has_email: bool | None = None
    has_whatsapp: bool | None = None
    category: str | None = None
    score_min: int | None = Field(default=None, ge=0, le=100)
    score_max: int | None = Field(default=None, ge=0, le=100)
    lead_source_type: LeadSourceType | None = None
    do_not_contact: bool | None = None
    sales_region_id: int | None = None
    market_segment_id: int | None = None
    market_subsegment_id: int | None = None
    assigned_sales_rep_id: int | None = None
    has_assignment: bool | None = None
    company_size_fit: CompanySizeFit | None = None
    trade_type: TradeType | None = None
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class LeadListResponse(BaseModel):
    total: int
    items: list[LeadSummary]


class LeadUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: LeadStatus | None = None
    notes: str | None = None
    tags: list[str] | None = None
    follow_up_date: date | None = None
    do_not_contact: bool | None = None


class LeadBatchEnrichmentRequest(BaseModel):
    lead_ids: list[int] = Field(min_length=1)


class EnrichmentRunResult(BaseModel):
    lead_id: int
    business_name: str
    pages_attempted: int
    pages_fetched: int
    contacts_added: int
    fields_updated: list[str]
    last_enriched_at: datetime
    material_profile: dict[str, Any] = Field(default_factory=dict)
    skipped_reason: str | None = None


class LeadBatchEnrichmentResponse(BaseModel):
    processed: int
    results: list[EnrichmentRunResult]
