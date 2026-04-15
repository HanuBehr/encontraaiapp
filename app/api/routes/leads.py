from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_app_settings, get_db_session
from app.config import Settings
from app.enums import CompanySizeFit, LeadSourceType, LeadStatus, TradeType
from app.repositories.lead_repository import LeadRepository
from app.schemas.lead import (
    LeadAssignmentRunResult,
    LeadAssignmentSuggestionRead,
    LeadBatchAssignmentRequest,
    LeadBatchAssignmentResponse,
    LeadBatchAssignmentSummary,
    LeadBatchEnrichmentRequest,
    LeadBatchEnrichmentResponse,
    LeadBlockedFilter,
    LeadDetail,
    LeadImportBatchResponse,
    LeadListFilters,
    LeadListResponse,
    LeadOptionsResponse,
    LeadScopeRequest,
    LeadScopeResolveResponse,
    LeadSummary,
    LeadSortBy,
    LeadSortDir,
    LeadUpdateRequest,
)
from app.services.crm import CRMService
from app.services.enrichment import EnrichmentService
from app.services.lead_assignment import LeadAssignmentService
from app.services.lead_scope import LeadScopeResolver, ResolvedLeadScope

router = APIRouter(prefix="/leads", tags=["leads"])


@router.get("", response_model=LeadListResponse)
def list_leads(
    city: str | None = Query(default=None),
    state: str | None = Query(default=None),
    status: LeadStatus | None = Query(default=None),
    has_email: bool | None = Query(default=None),
    has_whatsapp: bool | None = Query(default=None),
    has_instagram: bool | None = Query(default=None),
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
    company_size_fit: CompanySizeFit | None = Query(default=None),
    trade_type: TradeType | None = Query(default=None),
    blocked: LeadBlockedFilter = Query(default="exclude"),
    sort_by: LeadSortBy = Query(default="updated_at"),
    sort_dir: LeadSortDir = Query(default="desc"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db_session),
) -> LeadListResponse:
    filters = LeadListFilters(
        city=city,
        state=state,
        status=status,
        has_email=has_email,
        has_whatsapp=has_whatsapp,
        has_instagram=has_instagram,
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
        company_size_fit=company_size_fit,
        trade_type=trade_type,
        blocked=blocked,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
    repository = LeadRepository(db)
    leads, total = repository.list_leads(filters)
    return LeadListResponse(total=total, items=[LeadSummary.model_validate(lead) for lead in leads])


@router.get("/options", response_model=LeadOptionsResponse)
def get_lead_options(db: Session = Depends(get_db_session)) -> LeadOptionsResponse:
    repository = LeadRepository(db)
    assignment_options = repository.list_v2_filter_options()
    return LeadOptionsResponse(
        cities=repository.list_distinct_cities(),
        states=repository.list_distinct_states(),
        statuses=[status.value for status in LeadStatus],
        assigned_reps=assignment_options["assigned_reps"],
        sales_regions=assignment_options["sales_regions"],
        market_segments=assignment_options["market_segments"],
        market_subsegments=assignment_options["market_subsegments"],
        target_fit_values=[value.value for value in CompanySizeFit],
        trade_type_values=[value.value for value in TradeType],
    )


@router.get("/import-batches/latest", response_model=LeadImportBatchResponse)
def get_latest_import_batch(db: Session = Depends(get_db_session)) -> LeadImportBatchResponse:
    repository = LeadRepository(db)
    batch = repository.get_latest_completed_import_batch()
    if batch is None:
        raise HTTPException(status_code=404, detail="No completed import batch with leads was found.")
    lead_ids = repository.list_lead_ids_for_import_batch(batch.id)
    return _import_batch_response(batch, lead_ids)


@router.post("/resolve-scope", response_model=LeadScopeResolveResponse)
def resolve_lead_scope(
    payload: LeadScopeRequest,
    db: Session = Depends(get_db_session),
) -> LeadScopeResolveResponse:
    try:
        resolved = LeadScopeResolver(db).resolve(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _scope_response(resolved)


@router.post("/batch/enrich", response_model=LeadBatchEnrichmentResponse)
def enrich_lead_batch(
    payload: LeadBatchEnrichmentRequest,
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> LeadBatchEnrichmentResponse:
    service = EnrichmentService(db=db, settings=settings)
    try:
        response = service.enrich_lead_ids(
            payload.lead_ids,
            actor="api",
            scope_label="api lead ids",
            continue_on_error=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return response


@router.post("/batch/assign", response_model=LeadBatchAssignmentResponse)
def assign_lead_batch(
    payload: LeadBatchAssignmentRequest,
    db: Session = Depends(get_db_session),
) -> LeadBatchAssignmentResponse:
    try:
        resolved = LeadScopeResolver(db).resolve(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    service = LeadAssignmentService(db)
    result = service.apply_batch(
        lead_ids=resolved.lead_ids,
        overwrite=payload.overwrite,
        dry_run=payload.dry_run,
    )
    if not payload.dry_run:
        db.commit()
    return LeadBatchAssignmentResponse(
        processed=result.processed,
        changed=result.changed,
        dry_run=result.dry_run,
        results=[
            LeadAssignmentRunResult(
                lead_id=item.lead_id,
                changed_fields=item.changed_fields,
                suggestion=LeadAssignmentSuggestionRead(
                    sales_region_id=item.suggestion.sales_region_id,
                    market_segment_id=item.suggestion.market_segment_id,
                    market_subsegment_id=item.suggestion.market_subsegment_id,
                    assigned_sales_rep_id=item.suggestion.assigned_sales_rep_id,
                    assignment_rule_id=item.suggestion.assignment_rule_id,
                    explanation=item.suggestion.explanation,
                    metadata=item.suggestion.metadata,
                ),
            )
            for item in result.results
        ],
        summary=LeadBatchAssignmentSummary(
            scope_type=resolved.scope_type,
            scope_label=resolved.scope_label,
            requested=resolved.requested_count,
            processed=result.processed,
            changed=result.changed,
            overwrite=payload.overwrite,
            dry_run=payload.dry_run,
            missing_lead_ids=resolved.missing_lead_ids,
        ),
    )


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
        response = service.enrich_lead_ids(
            [lead_id],
            actor="api",
            scope_label="api single lead",
            continue_on_error=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return response


def _scope_response(resolved: ResolvedLeadScope) -> LeadScopeResolveResponse:
    import_batch = (
        _import_batch_response(resolved.import_batch, resolved.lead_ids)
        if resolved.import_batch is not None
        else None
    )
    return LeadScopeResolveResponse(
        scope_type=resolved.scope_type,
        scope_label=resolved.scope_label,
        total=len(resolved.lead_ids),
        lead_ids=resolved.lead_ids,
        missing_lead_ids=resolved.missing_lead_ids,
        import_batch=import_batch,
    )


def _import_batch_response(batch, lead_ids: list[int]) -> LeadImportBatchResponse:
    return LeadImportBatchResponse(
        id=batch.id,
        batch_type=batch.batch_type,
        status=batch.status,
        source_provider=batch.source_provider,
        source_query=batch.source_query,
        location_label=batch.location_label,
        record_count=batch.record_count,
        lead_count=len(lead_ids),
        lead_ids=lead_ids,
        started_at=batch.started_at,
        completed_at=batch.completed_at,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )
