from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.schemas.outreach import (
    DraftGenerateRequest,
    DraftPreviewRequest,
    DraftPreviewResponse,
    DraftRead,
    DraftStatusUpdateRequest,
    TemplateRead,
)
from app.services.outreach import OutreachService

router = APIRouter(prefix="/outreach", tags=["outreach"])


@router.get("/templates", response_model=list[TemplateRead])
def list_templates(db: Session = Depends(get_db_session)) -> list[TemplateRead]:
    service = OutreachService(db)
    return [TemplateRead.model_validate(template) for template in service.list_templates()]


@router.post("/leads/{lead_id}/preview", response_model=DraftPreviewResponse)
def preview_draft(
    lead_id: int,
    payload: DraftPreviewRequest,
    db: Session = Depends(get_db_session),
) -> DraftPreviewResponse:
    service = OutreachService(db)
    try:
        return service.preview_draft(lead_id, payload.template_key)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/leads/{lead_id}/generate", response_model=DraftRead)
def generate_draft(
    lead_id: int,
    payload: DraftGenerateRequest,
    db: Session = Depends(get_db_session),
) -> DraftRead:
    service = OutreachService(db)
    try:
        draft = service.generate_draft(lead_id, payload.template_key, actor="api")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DraftRead.model_validate(draft)


@router.get("/leads/{lead_id}/drafts", response_model=list[DraftRead])
def list_drafts_for_lead(lead_id: int, db: Session = Depends(get_db_session)) -> list[DraftRead]:
    service = OutreachService(db)
    return [DraftRead.model_validate(draft) for draft in service.list_drafts_for_lead(lead_id)]


@router.patch("/drafts/{draft_id}", response_model=DraftRead)
def update_draft_status(
    draft_id: int,
    payload: DraftStatusUpdateRequest,
    db: Session = Depends(get_db_session),
) -> DraftRead:
    service = OutreachService(db)
    try:
        draft = service.update_draft_status(
            draft_id,
            status=payload.status,
            rejected_reason=payload.rejected_reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DraftRead.model_validate(draft)
