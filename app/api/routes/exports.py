from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.enums import LeadSourceType, LeadStatus
from app.schemas.lead import LeadListFilters
from app.services.export_excel import ExcelExportService

router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("/excel")
def export_excel(
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
    db: Session = Depends(get_db_session),
) -> Response:
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
    )
    service = ExcelExportService(db)
    filename, payload = service.build_workbook(filters)
    return Response(
        content=payload,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
