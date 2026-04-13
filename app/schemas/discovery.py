from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.enums import LeadSourceType
from app.schemas.lead import LeadSummary


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


class DiscoveryPreviewItem(BaseModel):
    search_term: str
    provider_record_id: str | None = None
    source_url: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    candidate: DiscoveryLeadCandidate


class DiscoveryPreviewResponse(BaseModel):
    provider: str
    resolved_location: ResolvedLocation
    total_provider_results: int
    items: list[DiscoveryPreviewItem]
