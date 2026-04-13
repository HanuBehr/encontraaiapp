from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.enums import LeadSourceType, LeadStatus
from app.schemas.dedupe import (
    DedupePairRequest,
    DedupeRunRequest,
    DedupeRunResponse,
    DuplicatePreviewResponse,
)
from app.schemas.lead import LeadListFilters
from app.services.dedupe import DedupeService

router = APIRouter(prefix="/dedupe", tags=["dedupe"])


@router.get("/preview", response_model=DuplicatePreviewResponse)
def preview_duplicates(
    city: str | None = Query(default=None),
    status: LeadStatus | None = Query(default=None),
    has_email: bool | None = Query(default=None),
    has_whatsapp: bool | None = Query(default=None),
    category: str | None = Query(default=None),
    score_min: int | None = Query(default=None, ge=0, le=100),
    score_max: int | None = Query(default=None, ge=0, le=100),
    lead_source_type: LeadSourceType | None = Query(default=None),
    do_not_contact: bool | None = Query(default=None),
    db: Session = Depends(get_db_session),
) -> DuplicatePreviewResponse:
    filters = LeadListFilters(
        city=city,
        status=status,
        has_email=has_email,
        has_whatsapp=has_whatsapp,
        category=category,
        score_min=score_min,
        score_max=score_max,
        lead_source_type=lead_source_type,
        do_not_contact=do_not_contact,
    )
    service = DedupeService(db)
    return service.preview_duplicates(filters=filters)


@router.post("/pair", response_model=DedupeRunResponse)
def dedupe_pair(payload: DedupePairRequest, db: Session = Depends(get_db_session)) -> DedupeRunResponse:
    service = DedupeService(db)
    try:
        result = service.dedupe_pair(
            lead_a_id=payload.lead_a_id,
            lead_b_id=payload.lead_b_id,
            canonical_lead_id=payload.canonical_lead_id,
            actor="api",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DedupeRunResponse(processed=1, results=[result])


@router.post("/run", response_model=DedupeRunResponse)
def run_dedupe(payload: DedupeRunRequest | None = None, db: Session = Depends(get_db_session)) -> DedupeRunResponse:
    service = DedupeService(db)
    results = service.dedupe_batch(lead_ids=payload.lead_ids if payload else None, actor="api")
    return DedupeRunResponse(processed=len(results), results=results)
