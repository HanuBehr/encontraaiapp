from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.enums import (
    ActivityAction,
    CompanySizeFit,
    ContactType,
    ImportBatchStatus,
    ImportBatchType,
    LeadSourceType,
    LeadStatus,
    TradeType,
)
from app.schemas.common import ORMBaseModel


LeadSortBy = Literal[
    "id",
    "business_name",
    "city",
    "state",
    "status",
    "lead_score",
    "created_at",
    "updated_at",
    "last_enriched_at",
    "assigned_at",
    "company_size_fit",
    "trade_type",
]
LeadSortDir = Literal["asc", "desc"]
LeadBlockedFilter = Literal["exclude", "include", "only"]


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
    instagram: str | None = None
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
    is_blocked: bool = False
    blocked_reason: str | None = None
    blocked_rule_id: int | None = None
    blocked_at: datetime | None = None
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
    state: str | None = None
    status: LeadStatus | None = None
    has_email: bool | None = None
    has_whatsapp: bool | None = None
    has_instagram: bool | None = None
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
    import_batch_id: int | None = Field(default=None, ge=1)
    blocked: LeadBlockedFilter = "exclude"
    sort_by: LeadSortBy = "updated_at"
    sort_dir: LeadSortDir = "desc"
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class LeadListResponse(BaseModel):
    total: int
    items: list[LeadSummary]


class LeadNamedOption(BaseModel):
    id: int
    name: str


class LeadSalesRegionOption(LeadNamedOption):
    region_type: str
    state: str | None = None
    code: str | None = None


class LeadMarketSegmentOption(LeadNamedOption):
    key: str


class LeadMarketSubsegmentOption(LeadNamedOption):
    key: str
    market_segment_id: int


class LeadOptionsResponse(BaseModel):
    cities: list[str]
    states: list[str]
    statuses: list[str]
    assigned_reps: list[LeadNamedOption]
    sales_regions: list[LeadSalesRegionOption]
    market_segments: list[LeadMarketSegmentOption]
    market_subsegments: list[LeadMarketSubsegmentOption]
    target_fit_values: list[str]
    trade_type_values: list[str]


class LeadScopeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lead_ids: list[int] | None = Field(default=None, min_length=1)
    filters: LeadListFilters | None = None
    latest_import_batch: bool = False

    @model_validator(mode="after")
    def validate_exactly_one_scope(self) -> "LeadScopeRequest":
        scope_count = sum(
            [
                self.lead_ids is not None,
                self.filters is not None,
                self.latest_import_batch,
            ]
        )
        if scope_count != 1:
            raise ValueError("Provide exactly one lead scope: lead_ids, filters, or latest_import_batch.")
        return self


class LeadImportBatchResponse(BaseModel):
    id: int
    batch_type: ImportBatchType
    status: ImportBatchStatus
    source_provider: str | None = None
    source_query: str | None = None
    location_label: str | None = None
    record_count: int
    lead_count: int
    lead_ids: list[int]
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class LeadScopeResolveResponse(BaseModel):
    scope_type: str
    scope_label: str
    total: int
    lead_ids: list[int]
    missing_lead_ids: list[int] = Field(default_factory=list)
    import_batch: LeadImportBatchResponse | None = None


class LeadUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: LeadStatus | None = None
    notes: str | None = None
    tags: list[str] | None = None
    follow_up_date: date | None = None
    do_not_contact: bool | None = None


class LeadBatchEnrichmentRequest(BaseModel):
    lead_ids: list[int] = Field(min_length=1)


class EnrichmentAttemptedPage(BaseModel):
    url: str
    page_type: str | None = None
    discovered_from_url: str | None = None
    fetched: bool = False
    http_status: int | None = None
    robots_allowed: bool = True
    note: str | None = None


class EnrichmentExtractedContact(BaseModel):
    contact_type: ContactType
    raw_value: str
    normalized_value: str | None = None
    source_url: str
    confidence: float
    label: str | None = None
    note: str | None = None
    added_to_lead: bool = False


class EnrichmentRunResult(BaseModel):
    lead_id: int
    business_name: str | None = None
    success: bool = True
    pages_attempted: int = 0
    pages_fetched: int = 0
    attempted_pages: list[EnrichmentAttemptedPage] = Field(default_factory=list)
    fetched_page_urls: list[str] = Field(default_factory=list)
    extracted_contacts: list[EnrichmentExtractedContact] = Field(default_factory=list)
    contacts_added: int = 0
    contacts_added_by_type: dict[str, int] = Field(default_factory=dict)
    fields_updated: list[str] = Field(default_factory=list)
    last_enriched_at: datetime | None = None
    material_profile: dict[str, Any] = Field(default_factory=dict)
    skipped_reason: str | None = None
    no_email_found: bool = False
    error_message: str | None = None


class LeadBatchEnrichmentSummary(BaseModel):
    scope_label: str | None = None
    requested: int = 0
    processed: int = 0
    success_count: int = 0
    contacts_added: int = 0
    emails_found: int = 0
    instagrams_found: int = 0
    whatsapps_found: int = 0
    contact_forms_found: int = 0
    skipped: int = 0
    skipped_no_website: int = 0
    errors: int = 0
    error_messages: list[str] = Field(default_factory=list)
    failed_lead_ids: list[int] = Field(default_factory=list)
    pages_attempted: int = 0
    pages_fetched: int = 0


class LeadBatchEnrichmentResponse(BaseModel):
    processed: int
    results: list[EnrichmentRunResult]
    summary: LeadBatchEnrichmentSummary = Field(default_factory=LeadBatchEnrichmentSummary)


class LeadAssignmentSuggestionRead(BaseModel):
    sales_region_id: int | None = None
    market_segment_id: int | None = None
    market_subsegment_id: int | None = None
    assigned_sales_rep_id: int | None = None
    assignment_rule_id: int | None = None
    explanation: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LeadAssignmentRunResult(BaseModel):
    lead_id: int
    changed_fields: list[str]
    suggestion: LeadAssignmentSuggestionRead


class LeadBatchAssignmentRequest(LeadScopeRequest):
    overwrite: bool = False
    dry_run: bool = False


class LeadBatchAssignmentSummary(BaseModel):
    scope_type: str
    scope_label: str
    requested: int
    processed: int
    changed: int
    overwrite: bool
    dry_run: bool
    missing_lead_ids: list[int] = Field(default_factory=list)


class LeadBatchAssignmentResponse(BaseModel):
    processed: int
    changed: int
    dry_run: bool
    results: list[LeadAssignmentRunResult]
    summary: LeadBatchAssignmentSummary
