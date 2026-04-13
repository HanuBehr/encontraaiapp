from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.schemas.scoring import ScoreBatchRequest, ScoreBatchResponse, ScoreResult
from app.services.scoring import ScoringService

router = APIRouter(prefix="/scoring", tags=["scoring"])


@router.post("/{lead_id}/rescore", response_model=ScoreResult)
def rescore_lead(lead_id: int, db: Session = Depends(get_db_session)) -> ScoreResult:
    service = ScoringService(db)
    try:
        result = service.score_lead(lead_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return result


@router.post("/run", response_model=ScoreBatchResponse)
def run_scoring(
    payload: ScoreBatchRequest | None = None,
    db: Session = Depends(get_db_session),
) -> ScoreBatchResponse:
    service = ScoringService(db)
    results = service.score_batch(lead_ids=payload.lead_ids if payload else None)
    return ScoreBatchResponse(processed=len(results), results=results)
