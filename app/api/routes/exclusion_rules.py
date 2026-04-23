from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.schemas.exclusion_rule import (
    ExclusionApplySummaryRead,
    ExclusionRuleCreateRequest,
    ExclusionRuleCreateResponse,
    ExclusionRuleRead,
)
from app.services.exclusion_rules import ExclusionRuleService

router = APIRouter(prefix="/exclusion-rules", tags=["exclusion-rules"])


@router.post("", response_model=ExclusionRuleCreateResponse)
def create_exclusion_rule(
    payload: ExclusionRuleCreateRequest,
    db: Session = Depends(get_db_session),
) -> ExclusionRuleCreateResponse:
    service = ExclusionRuleService(db)
    try:
        rule = service.create_rule(
            rule_type=payload.rule_type,
            pattern=payload.pattern,
            reason=payload.reason,
            is_active=payload.is_active,
        )
        summary = service.reapply_all() if payload.reapply_existing_leads else None
        db.commit()
        db.refresh(rule)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ExclusionRuleCreateResponse(
        rule=ExclusionRuleRead.model_validate(rule),
        reapply_summary=(
            ExclusionApplySummaryRead(
                evaluated=summary.evaluated,
                blocked=summary.blocked,
                unblocked=summary.unblocked,
                unchanged=summary.unchanged,
            )
            if summary is not None
            else None
        ),
    )
