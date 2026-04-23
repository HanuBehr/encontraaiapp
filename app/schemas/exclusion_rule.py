from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ORMBaseModel


InlineExclusionRuleType = Literal["exact_name", "business_name_contains", "domain"]


class ExclusionRuleCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_type: InlineExclusionRuleType
    pattern: str = Field(min_length=1)
    reason: str | None = None
    is_active: bool = True
    reapply_existing_leads: bool = True


class ExclusionApplySummaryRead(BaseModel):
    evaluated: int
    blocked: int
    unblocked: int
    unchanged: int


class ExclusionRuleRead(ORMBaseModel):
    id: int
    organization_id: int
    rule_type: str
    pattern: str
    normalized_pattern: str
    reason: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ExclusionRuleCreateResponse(BaseModel):
    rule: ExclusionRuleRead
    reapply_summary: ExclusionApplySummaryRead | None = None
