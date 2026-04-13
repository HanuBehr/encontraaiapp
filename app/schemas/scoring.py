from __future__ import annotations

from pydantic import BaseModel, Field


class ScoreResult(BaseModel):
    lead_id: int
    lead_score: int
    breakdown: dict[str, object] = Field(default_factory=dict)


class ScoreBatchRequest(BaseModel):
    lead_ids: list[int] | None = None


class ScoreBatchResponse(BaseModel):
    processed: int
    results: list[ScoreResult]
