from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.enums import ImportBatchStatus, LeadSourceType
from app.schemas.lead import EnrichmentAttemptedPage, EnrichmentExtractedContact, LeadSummary


class ResolvedLocation(BaseModel):
    label: str
    latitude: float
    longitude: float


class DiscoveryLeadCandidate(BaseModel):
    business_name: str
    normalized_business_name: str
    category: str | None = None
    address: str | None = None
    neighborhood: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    website: str | None = None
    domain: str | None = None
    email: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    instagram: str | None = None
    google_maps_url: str | None = None
    google_place_id: str | None = None
    source_provider: str
    source_url: str | None = None
    lead_source_type: LeadSourceType


class DiscoverySearchRequest(BaseModel):
    search_terms: list[str] = Field(min_length=1)
    location_query: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    radius_m: int = Field(default=3000, ge=100, le=50000)
    max_results_per_term: int = Field(default=10, ge=1, le=20)

    @model_validator(mode="after")
    def validate_location(self) -> "DiscoverySearchRequest":
        has_query = bool(self.location_query)
        has_coordinates = self.latitude is not None and self.longitude is not None
        if not has_query and not has_coordinates:
            raise ValueError("Provide either location_query or latitude/longitude.")
        if (self.latitude is None) ^ (self.longitude is None):
            raise ValueError("Latitude and longitude must be provided together.")
        return self


class DiscoverySearchResponse(BaseModel):
    batch_id: int
    provider: str
    resolved_location: ResolvedLocation
    total_provider_results: int
    created_leads: int
    updated_leads: int
    leads: list[LeadSummary]


class DiscoveryExclusionMetadata(BaseModel):
    is_blocked: bool = False
    rule_id: int | None = None
    rule_type: str | None = None
    pattern: str | None = None
    reason: str | None = None


class DiscoveryPreviewItem(BaseModel):
    client_result_id: str | None = None
    search_term: str
    provider_record_id: str | None = None
    source_url: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    candidate: DiscoveryLeadCandidate
    exclusion: DiscoveryExclusionMetadata = Field(default_factory=DiscoveryExclusionMetadata)
    enrichment: "DiscoveryPreviewEnrichmentMetadata | None" = None


class DiscoveryPreviewResponse(BaseModel):
    provider: str
    resolved_location: ResolvedLocation
    total_provider_results: int
    items: list[DiscoveryPreviewItem]


class DiscoveryEvaluateExclusionsRequest(BaseModel):
    preview: DiscoveryPreviewResponse


class DiscoveryPreviewEnrichmentMetadata(BaseModel):
    success: bool = True
    attempted_pages: list[EnrichmentAttemptedPage] = Field(default_factory=list)
    fetched_page_urls: list[str] = Field(default_factory=list)
    extracted_contacts: list[EnrichmentExtractedContact] = Field(default_factory=list)
    email_found: bool = False
    instagram_found: bool = False
    contact_form_found: bool = False
    no_email_found: bool = False
    skipped_reason: str | None = None
    error_message: str | None = None


class DiscoveryPreviewEnrichmentRequest(BaseModel):
    preview: DiscoveryPreviewResponse
    client_result_ids: list[str] = Field(min_length=1, max_length=25)
    skip_blocked: bool = True


class DiscoveryPreviewEnrichmentSummary(BaseModel):
    requested: int
    processed: int
    success_count: int = 0
    emails_found: int = 0
    instagrams_found: int = 0
    contact_forms_found: int = 0
    no_email_found: int = 0
    skipped_no_website: int = 0
    blocked_after_enrichment: int = 0
    errors: int = 0
    error_messages: list[str] = Field(default_factory=list)


class DiscoveryPreviewEnrichmentResponse(BaseModel):
    preview: DiscoveryPreviewResponse
    summary: DiscoveryPreviewEnrichmentSummary


class DiscoveryPreviewWebsiteRecoveryRequest(BaseModel):
    preview: DiscoveryPreviewResponse
    client_result_ids: list[str] = Field(min_length=1, max_length=25)
    skip_blocked: bool = True


class DiscoveryPreviewWebsiteRecoverySummary(BaseModel):
    requested: int
    processed: int
    recovered_count: int = 0
    no_website_found: int = 0
    skipped_existing_website: int = 0
    skipped_missing_place_id: int = 0
    skipped_blocked: int = 0
    blocked_after_recovery: int = 0
    errors: int = 0
    error_messages: list[str] = Field(default_factory=list)


class DiscoveryPreviewWebsiteRecoveryResponse(BaseModel):
    preview: DiscoveryPreviewResponse
    summary: DiscoveryPreviewWebsiteRecoverySummary


class DiscoveryImportRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    search_request: DiscoverySearchRequest = Field(alias="request")
    preview: DiscoveryPreviewResponse
    selected_client_result_ids: list[str] = Field(min_length=1)
    skip_blocked: bool = True


class DiscoveryImportBatchSummary(BaseModel):
    id: int
    status: ImportBatchStatus
    source_provider: str | None = None
    source_query: str | None = None
    location_label: str | None = None
    record_count: int
    lead_count: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class DiscoveryImportSkippedItem(BaseModel):
    client_result_id: str
    business_name: str
    reason: str
    exclusion: DiscoveryExclusionMetadata


class DiscoveryImportResponse(BaseModel):
    batch: DiscoveryImportBatchSummary
    batch_id: int
    provider: str
    resolved_location: ResolvedLocation
    total_preview_items: int
    selected_items: int
    saved_items: int
    skipped_blocked: int
    created_leads: int
    updated_leads: int
    saved_lead_ids: list[int]
    leads: list[LeadSummary]
    skipped_items: list[DiscoveryImportSkippedItem] = Field(default_factory=list)
