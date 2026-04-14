from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_app_settings, get_db_session
from app.config import Settings
from app.enums import LeadSourceType, LeadStatus
from app.repositories.lead_repository import LeadRepository
from app.schemas.lead import (
    LeadBatchEnrichmentRequest,
    LeadBatchEnrichmentResponse,
    LeadDetail,
    LeadListFilters,
    LeadListResponse,
    LeadSummary,
    LeadUpdateRequest,
)
from app.services.crm import CRMService
from app.services.enrichment import EnrichmentService

router = APIRouter(prefix="/leads", tags=["leads"])


@router.get("", response_model=LeadListResponse)
def list_leads(
    city: str | None = Query(default=None),
    status: LeadStatus | None = Query(default=None),
    has_email: bool | None = Query(default=None),
    has_whatsapp: bool | None = Query(default=None),
    category: str | None = Query(default=None),
    score_min: int | None = Query(default=None, ge=0, le=100),
    score_max: int | None = Query(default=None, ge=0, le=100),
    lead_source_type: LeadSourceType | None = Query(default=None),
    do_not_contact: bool | None = Query(default=None),
    sales_region_id: int | None = Query(default=None),
    market_segment_id: int | None = Query(default=None),
    market_subsegment_id: int | None = Query(default=None),
    assigned_sales_rep_id: int | None = Query(default=None),
    has_assignment: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db_session),
) -> LeadListResponse:
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
        sales_region_id=sales_region_id,
        market_segment_id=market_segment_id,
        market_subsegment_id=market_subsegment_id,
        assigned_sales_rep_id=assigned_sales_rep_id,
        has_assignment=has_assignment,
        limit=limit,
        offset=offset,
    )
    repository = LeadRepository(db)
    leads, total = repository.list_leads(filters)
    return LeadListResponse(total=total, items=[LeadSummary.model_validate(lead) for lead in leads])


@router.post("/batch/enrich", response_model=LeadBatchEnrichmentResponse)
def enrich_lead_batch(
    payload: LeadBatchEnrichmentRequest,
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> LeadBatchEnrichmentResponse:
    service = EnrichmentService(db=db, settings=settings)
    try:
        results = service.enrich_batch(payload.lead_ids, actor="api")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return LeadBatchEnrichmentResponse(processed=len(results), results=results)


@router.get("/{lead_id}", response_model=LeadDetail)
def get_lead_detail(lead_id: int, db: Session = Depends(get_db_session)) -> LeadDetail:
    repository = LeadRepository(db)
    lead = repository.get_detail(lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found.")
    return LeadDetail.model_validate(lead)


@router.patch("/{lead_id}", response_model=LeadDetail)
def update_lead(
    lead_id: int,
    payload: LeadUpdateRequest,
    db: Session = Depends(get_db_session),
) -> LeadDetail:
    service = CRMService(db)
    try:
        lead = service.update_lead(lead_id, payload, actor="api")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return LeadDetail.model_validate(lead)


@router.post("/{lead_id}/enrich", response_model=LeadBatchEnrichmentResponse)
def enrich_single_lead(
    lead_id: int,
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> LeadBatchEnrichmentResponse:
    service = EnrichmentService(db=db, settings=settings)
    try:
        result = service.enrich_lead(lead_id, actor="api")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return LeadBatchEnrichmentResponse(processed=1, results=[result])
