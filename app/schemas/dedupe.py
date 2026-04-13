from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.lead import LeadSummary


class DuplicateCandidate(BaseModel):
    lead_a: LeadSummary
    lead_b: LeadSummary
    reasons: list[str]
    confidence: float
    recommended_canonical_id: int


class DuplicatePreviewResponse(BaseModel):
    total_candidates: int
    items: list[DuplicateCandidate]


class DedupePairRequest(BaseModel):
    lead_a_id: int
    lead_b_id: int
    canonical_lead_id: int | None = None


class DedupeRunRequest(BaseModel):
    lead_ids: list[int] | None = None


class DedupeResult(BaseModel):
    canonical_lead_id: int
    duplicate_lead_id: int
    duplicate_reason: str
    merged_fields: list[str] = Field(default_factory=list)


class DedupeRunResponse(BaseModel):
    processed: int
    results: list[DedupeResult]
