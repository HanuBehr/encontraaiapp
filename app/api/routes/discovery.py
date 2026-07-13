from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_app_settings, get_db_session
from app.config import Settings
from app.schemas.discovery import (
    DiscoveryEvaluateExclusionsRequest,
    DiscoveryImportRequest,
    DiscoveryImportResponse,
    DiscoveryPreviewEnrichmentRequest,
    DiscoveryPreviewEnrichmentResponse,
    DiscoveryPreviewResponse,
    DiscoveryPreviewWebsiteRecoveryRequest,
    DiscoveryPreviewWebsiteRecoveryResponse,
    DiscoverySearchRequest,
    DiscoverySearchResponse,
)
from app.services.discovery import DiscoveryService
from app.services.observability import new_correlation_id, operation_log
from app.services.providers.google_places import GooglePlacesProviderError

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.post("/preview", response_model=DiscoveryPreviewResponse)
def preview_discovery_search(
    payload: DiscoverySearchRequest,
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> DiscoveryPreviewResponse:
    correlation_id = new_correlation_id("discovery-preview")
    operation_log("discovery.preview_started", correlation_id=correlation_id, terms=len(payload.search_terms), max_results_per_term=payload.max_results_per_term)
    service = DiscoveryService(db=db, settings=settings)
    try:
        response = service.preview(payload)
        operation_log("discovery.preview_completed", correlation_id=correlation_id, results=len(response.items), duplicates_removed=response.duplicates_removed)
        return response
    except GooglePlacesProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/evaluate-exclusions", response_model=DiscoveryPreviewResponse)
def evaluate_discovery_exclusions(
    payload: DiscoveryEvaluateExclusionsRequest,
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> DiscoveryPreviewResponse:
    service = DiscoveryService(db=db, settings=settings)
    return service.evaluate_preview_exclusions(payload.preview)


@router.post("/import", response_model=DiscoveryImportResponse)
def import_discovery_preview(
    payload: DiscoveryImportRequest,
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> DiscoveryImportResponse:
    correlation_id = new_correlation_id("discovery-import")
    operation_log("discovery.import_started", correlation_id=correlation_id, selected=len(payload.selected_client_result_ids))
    service = DiscoveryService(db=db, settings=settings)
    try:
        response = service.import_preview(
            request=payload.search_request,
            preview=payload.preview,
            selected_client_result_ids=payload.selected_client_result_ids,
            skip_blocked=payload.skip_blocked,
        )
        operation_log("discovery.import_completed", correlation_id=correlation_id, created=response.created_count, skipped_existing=response.skipped_existing_count)
        return response
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/enrich-preview", response_model=DiscoveryPreviewEnrichmentResponse)
def enrich_discovery_preview(
    payload: DiscoveryPreviewEnrichmentRequest,
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> DiscoveryPreviewEnrichmentResponse:
    correlation_id = new_correlation_id("preview-enrich")
    operation_log("enrichment.preview_started", correlation_id=correlation_id, requested=len(payload.client_result_ids))
    service = DiscoveryService(db=db, settings=settings)
    try:
        response = service.enrich_preview(
            preview=payload.preview,
            client_result_ids=payload.client_result_ids,
            skip_blocked=payload.skip_blocked,
        )
        operation_log("enrichment.preview_completed", correlation_id=correlation_id, processed=response.summary.processed, errors=response.summary.errors)
        return response
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/recover-websites", response_model=DiscoveryPreviewWebsiteRecoveryResponse)
def recover_discovery_preview_websites(
    payload: DiscoveryPreviewWebsiteRecoveryRequest,
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> DiscoveryPreviewWebsiteRecoveryResponse:
    service = DiscoveryService(db=db, settings=settings)
    try:
        return service.recover_preview_websites(
            preview=payload.preview,
            client_result_ids=payload.client_result_ids,
            skip_blocked=payload.skip_blocked,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/search", response_model=DiscoverySearchResponse)
def run_discovery_search(
    payload: DiscoverySearchRequest,
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> DiscoverySearchResponse:
    service = DiscoveryService(db=db, settings=settings)
    try:
        return service.search(payload)
    except GooglePlacesProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
