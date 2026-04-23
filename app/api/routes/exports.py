from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.enums import CompanySizeFit, LeadSourceType, LeadStatus, TradeType
from app.schemas.lead import LeadBlockedFilter, LeadListFilters, LeadScopeRequest, LeadSortBy, LeadSortDir
from app.services.export_excel import ExcelExportService
from app.services.lead_scope import LeadScopeResolver

router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("/excel")
def export_excel(
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
    import_batch_id: int | None = Query(default=None, ge=1),
    blocked: LeadBlockedFilter = Query(default="exclude"),
    sort_by: LeadSortBy = Query(default="updated_at"),
    sort_dir: LeadSortDir = Query(default="desc"),
    db: Session = Depends(get_db_session),
) -> Response:
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
        import_batch_id=import_batch_id,
        blocked=blocked,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    service = ExcelExportService(db)
    filename, payload = service.build_workbook(filters)
    return _excel_response(filename, payload)


@router.post("/excel")
def export_excel_for_scope(
    payload: LeadScopeRequest,
    db: Session = Depends(get_db_session),
) -> Response:
    try:
        resolved = LeadScopeResolver(db).resolve(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    service = ExcelExportService(db)
    filename, workbook_payload = service.build_workbook(
        resolved.filters,
        lead_ids=resolved.lead_ids,
        scope_label=resolved.scope_label,
        scope_metadata=resolved.metadata,
    )
    return _excel_response(filename, workbook_payload)


def _excel_response(filename: str, payload: bytes) -> Response:
    return Response(
        content=payload,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
