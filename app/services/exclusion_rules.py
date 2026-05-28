from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.lead import Lead
from app.models.lead_exclusion_rule import LeadExclusionRule
from app.repositories.organization_repository import get_or_create_default_organization
from app.schemas.discovery import DiscoveryLeadCandidate
from app.services.normalization import normalize_business_name, normalize_domain, normalize_text


EXCLUSION_RULE_TYPES = {
    "exact_name",
    "business_name_contains",
    "domain",
    "provider_category",
}


@dataclass(slots=True)
class ExclusionMatch:
    rule_id: int
    rule_type: str
    pattern: str
    reason: str


@dataclass(slots=True)
class ExclusionApplySummary:
    evaluated: int
    blocked: int
    unblocked: int
    unchanged: int


class ExclusionRuleService:
    def __init__(self, db: Session, organization_id: int | None = None) -> None:
        self.db = db
        self._organization_id = organization_id
        self._active_rule_cache: list[LeadExclusionRule] | None = None

    @property
    def organization_id(self) -> int:
        if self._organization_id is None:
            self._organization_id = get_or_create_default_organization(self.db).id
        return self._organization_id

    def create_rule(
        self,
        *,
        rule_type: str,
        pattern: str,
        reason: str | None = None,
        is_active: bool = True,
    ) -> LeadExclusionRule:
        normalized_rule_type = self._validate_rule_type(rule_type)
        normalized_pattern = normalize_rule_pattern(normalized_rule_type, pattern)
        if not normalized_pattern:
            raise ValueError("Exclusion rule pattern cannot be empty.")

        existing = self.db.execute(
            select(LeadExclusionRule).where(
                LeadExclusionRule.organization_id == self.organization_id,
                LeadExclusionRule.rule_type == normalized_rule_type,
                LeadExclusionRule.normalized_pattern == normalized_pattern,
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.pattern = pattern.strip()
            existing.reason = reason
            existing.is_active = is_active
            self.db.flush()
            self._active_rule_cache = None
            return existing

        rule = LeadExclusionRule(
            organization_id=self.organization_id,
            rule_type=normalized_rule_type,
            pattern=pattern.strip(),
            normalized_pattern=normalized_pattern,
            reason=reason,
            is_active=is_active,
        )
        self.db.add(rule)
        self.db.flush()
        self._active_rule_cache = None
        return rule

    def evaluate_lead(self, lead: Lead) -> ExclusionMatch | None:
        payload = _LeadExclusionPayload(
            business_name=lead.business_name,
            normalized_business_name=lead.normalized_business_name,
            category=lead.category,
            website=lead.website,
            domain=lead.domain,
        )
        return self._evaluate(payload)

    def evaluate_candidate(self, candidate: DiscoveryLeadCandidate) -> ExclusionMatch | None:
        payload = _LeadExclusionPayload(
            business_name=candidate.business_name,
            normalized_business_name=candidate.normalized_business_name,
            category=candidate.category,
            website=candidate.website,
            domain=candidate.domain,
        )
        return self._evaluate(payload)

    def apply_to_lead(self, lead: Lead) -> ExclusionMatch | None:
        match = self.evaluate_lead(lead)
        if match is None:
            if lead.is_blocked:
                lead.is_blocked = False
                lead.blocked_reason = None
                lead.blocked_rule_id = None
                lead.blocked_at = None
            self.db.flush()
            return None

        should_refresh_blocked_at = not lead.is_blocked or lead.blocked_rule_id != match.rule_id
        lead.is_blocked = True
        lead.blocked_reason = match.reason
        lead.blocked_rule_id = match.rule_id
        if should_refresh_blocked_at:
            lead.blocked_at = utcnow()
        self.db.flush()
        return match

    def reapply_all(self) -> ExclusionApplySummary:
        self._active_rule_cache = None
        leads = self.db.execute(
            select(Lead)
            .where(or_(Lead.organization_id == self.organization_id, Lead.organization_id.is_(None)))
            .order_by(Lead.id.asc())
        ).scalars().all()

        blocked = 0
        unblocked = 0
        unchanged = 0
        for lead in leads:
            was_blocked = bool(lead.is_blocked)
            match = self.apply_to_lead(lead)
            is_blocked = match is not None
            if is_blocked and not was_blocked:
                blocked += 1
            elif was_blocked and not is_blocked:
                unblocked += 1
            else:
                unchanged += 1

        self.db.flush()
        return ExclusionApplySummary(
            evaluated=len(leads),
            blocked=blocked,
            unblocked=unblocked,
            unchanged=unchanged,
        )

    def _evaluate(self, payload: "_LeadExclusionPayload") -> ExclusionMatch | None:
        rules = self.active_rules()
        for rule in rules:
            if self._rule_matches(rule, payload):
                reason = rule.reason or f"Matched exclusion rule: {rule.rule_type}={rule.pattern}"
                return ExclusionMatch(
                    rule_id=rule.id,
                    rule_type=rule.rule_type,
                    pattern=rule.pattern,
                    reason=reason,
                )
        return None

    def active_rules(self) -> list[LeadExclusionRule]:
        if self._active_rule_cache is None:
            self._active_rule_cache = self._load_active_rules()
        return self._active_rule_cache

    def _load_active_rules(self) -> list[LeadExclusionRule]:
        return list(
            self.db.execute(
                select(LeadExclusionRule)
                .where(
                    LeadExclusionRule.organization_id == self.organization_id,
                    LeadExclusionRule.is_active.is_(True),
                )
                .order_by(LeadExclusionRule.id.asc())
            ).scalars().all()
        )

    @staticmethod
    def _rule_matches(rule: LeadExclusionRule, payload: "_LeadExclusionPayload") -> bool:
        if rule.rule_type == "exact_name":
            return bool(payload.normalized_name and payload.normalized_name == rule.normalized_pattern)
        if rule.rule_type == "business_name_contains":
            return bool(payload.normalized_name and rule.normalized_pattern in payload.normalized_name)
        if rule.rule_type == "domain":
            return any(
                domain == rule.normalized_pattern or domain.endswith(f".{rule.normalized_pattern}")
                for domain in payload.domains
            )
        if rule.rule_type == "provider_category":
            return bool(payload.normalized_category and payload.normalized_category == rule.normalized_pattern)
        return False

    @staticmethod
    def _validate_rule_type(rule_type: str) -> str:
        normalized_rule_type = (rule_type or "").strip().lower()
        if normalized_rule_type not in EXCLUSION_RULE_TYPES:
            allowed = ", ".join(sorted(EXCLUSION_RULE_TYPES))
            raise ValueError(f"Unsupported exclusion rule type '{rule_type}'. Allowed values: {allowed}.")
        return normalized_rule_type


@dataclass(slots=True)
class _LeadExclusionPayload:
    business_name: str | None
    normalized_business_name: str | None
    category: str | None
    website: str | None
    domain: str | None

    @property
    def normalized_name(self) -> str | None:
        return normalize_business_name(self.normalized_business_name or self.business_name)

    @property
    def normalized_category(self) -> str | None:
        return normalize_text(self.category)

    @property
    def domains(self) -> list[str]:
        candidates = [normalize_domain(self.domain), normalize_domain(self.website)]
        return list(dict.fromkeys(value for value in candidates if value))


def normalize_rule_pattern(rule_type: str, pattern: str | None) -> str | None:
    if not pattern:
        return None
    if rule_type == "domain":
        return normalize_domain(pattern)
    return normalize_text(pattern)
