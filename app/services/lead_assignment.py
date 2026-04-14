from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.assignment_rule import AssignmentRule
from app.models.base import utcnow
from app.models.lead import Lead
from app.models.market_taxonomy import MarketSegment, MarketSubsegment
from app.models.sales_region import SalesRegion
from app.repositories.lead_repository import LeadRepository
from app.schemas.lead import LeadListFilters
from app.services.normalization import normalize_text


@dataclass(slots=True)
class LeadAssignmentSuggestion:
    sales_region_id: int | None = None
    market_segment_id: int | None = None
    market_subsegment_id: int | None = None
    assigned_sales_rep_id: int | None = None
    assignment_rule_id: int | None = None
    explanation: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LeadAssignmentResult:
    lead_id: int
    changed_fields: list[str]
    suggestion: LeadAssignmentSuggestion


@dataclass(slots=True)
class LeadAssignmentBatchResult:
    processed: int
    changed: int
    dry_run: bool
    results: list[LeadAssignmentResult]


@dataclass(slots=True)
class _SubsegmentMatch:
    subsegment: MarketSubsegment
    matched_keywords: list[str]


class LeadAssignmentService:
    def __init__(self, db: Session, organization_id: int | None = None) -> None:
        self.db = db
        self.repository = LeadRepository(db, organization_id=organization_id)

    def evaluate_lead(self, lead: Lead) -> LeadAssignmentSuggestion:
        organization_id = lead.organization_id or self.repository.organization_id
        region = self._match_sales_region(lead, organization_id)
        subsegment_match = self._match_market_subsegment(lead, organization_id)
        segment = subsegment_match.subsegment.segment if subsegment_match else None
        rule = self._match_assignment_rule(
            organization_id=organization_id,
            sales_region_id=region.id if region else None,
            market_segment_id=segment.id if segment else None,
            market_subsegment_id=subsegment_match.subsegment.id if subsegment_match else None,
        )

        return LeadAssignmentSuggestion(
            sales_region_id=region.id if region else None,
            market_segment_id=segment.id if segment else None,
            market_subsegment_id=subsegment_match.subsegment.id if subsegment_match else None,
            assigned_sales_rep_id=rule.sales_rep_id if rule else None,
            assignment_rule_id=rule.id if rule else None,
            explanation=self._build_explanation(
                region=region,
                subsegment_match=subsegment_match,
                rule=rule,
            ),
            metadata=self._build_metadata(
                region=region,
                lead=lead,
                segment=segment,
                subsegment_match=subsegment_match,
                rule=rule,
            ),
        )

    def apply_to_lead(self, lead_id: int, *, overwrite: bool = False) -> LeadAssignmentResult:
        lead = self.repository.get_by_id(lead_id)
        if lead is None:
            raise ValueError(f"Lead {lead_id} not found in organization scope.")

        return self._apply_to_loaded_lead(lead, overwrite=overwrite)

    def apply_batch(
        self,
        *,
        lead_ids: Iterable[int] | None = None,
        filters: LeadListFilters | None = None,
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> LeadAssignmentBatchResult:
        if lead_ids is not None:
            leads = self.repository.get_by_ids(lead_ids)
        else:
            leads = self.repository.list_all_leads(filters)

        results = [
            self._apply_to_loaded_lead(lead, overwrite=overwrite, dry_run=dry_run)
            for lead in leads
        ]
        if not dry_run:
            self.db.flush()

        return LeadAssignmentBatchResult(
            processed=len(results),
            changed=sum(1 for result in results if result.changed_fields),
            dry_run=dry_run,
            results=results,
        )

    def _apply_to_loaded_lead(
        self,
        lead: Lead,
        *,
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> LeadAssignmentResult:
        suggestion = self.evaluate_lead(lead)
        changed_fields = self._assignment_changed_fields(lead, suggestion, overwrite=overwrite)

        if not dry_run:
            self._apply_suggestion(lead, suggestion, changed_fields=changed_fields, overwrite=overwrite)
            self.db.flush()
        return LeadAssignmentResult(
            lead_id=lead.id,
            changed_fields=list(dict.fromkeys(changed_fields)),
            suggestion=suggestion,
        )

    def _match_sales_region(self, lead: Lead, organization_id: int) -> SalesRegion | None:
        lead_city = normalize_text(lead.city)
        lead_state = normalize_text(lead.state)
        query = (
            select(SalesRegion)
            .where(SalesRegion.organization_id == organization_id, SalesRegion.is_active.is_(True))
            .order_by(SalesRegion.region_type.asc(), SalesRegion.name.asc(), SalesRegion.id.asc())
        )
        regions = self.db.execute(query).scalars().all()
        eligible_regions = [
            region
            for region in regions
            if self._state_matches(lead_state=lead_state, region=region)
        ]

        for region in eligible_regions:
            if self._postal_code_matches(lead, region):
                return region

        for region in eligible_regions:
            if self._neighborhood_matches(lead, region):
                return region

        if not lead_city:
            return None

        for region in eligible_regions:
            if self._requires_neighborhood_match(region):
                continue
            if lead_city not in self._normalized_cities(region):
                continue
            return region
        return None

    def _match_market_subsegment(self, lead: Lead, organization_id: int) -> _SubsegmentMatch | None:
        lead_text = self._lead_text(lead)
        if not lead_text:
            return None

        query = (
            select(MarketSubsegment)
            .join(MarketSegment, MarketSubsegment.segment_id == MarketSegment.id)
            .options(selectinload(MarketSubsegment.segment))
            .where(
                MarketSubsegment.organization_id == organization_id,
                MarketSubsegment.is_active.is_(True),
                MarketSegment.organization_id == organization_id,
                MarketSegment.is_active.is_(True),
            )
            .order_by(MarketSubsegment.sort_order.asc(), MarketSubsegment.name.asc(), MarketSubsegment.id.asc())
        )
        for subsegment in self.db.execute(query).scalars().all():
            matched_keywords = [
                keyword
                for keyword in subsegment.keywords_json or []
                if (normalized_keyword := normalize_text(keyword)) and normalized_keyword in lead_text
            ]
            if matched_keywords:
                return _SubsegmentMatch(subsegment=subsegment, matched_keywords=matched_keywords)
        return None

    def _assignment_changed_fields(
        self,
        lead: Lead,
        suggestion: LeadAssignmentSuggestion,
        *,
        overwrite: bool,
    ) -> list[str]:
        changed_fields: list[str] = []

        assignment_rule_value = suggestion.assignment_rule_id
        if not overwrite and lead.assigned_sales_rep_id is not None:
            assignment_rule_value = None

        for field_name, value in [
            ("sales_region_id", suggestion.sales_region_id),
            ("market_segment_id", suggestion.market_segment_id),
            ("market_subsegment_id", suggestion.market_subsegment_id),
            ("assigned_sales_rep_id", suggestion.assigned_sales_rep_id),
            ("assignment_rule_id", assignment_rule_value),
        ]:
            current_value = getattr(lead, field_name)
            if overwrite:
                if current_value != value:
                    changed_fields.append(field_name)
            elif current_value is None and value is not None:
                changed_fields.append(field_name)

        if overwrite or changed_fields or not lead.assignment_metadata_json:
            if lead.assignment_explanation != suggestion.explanation:
                changed_fields.append("assignment_explanation")
            if lead.assignment_metadata_json != suggestion.metadata:
                changed_fields.append("assignment_metadata_json")
            changed_fields.append("assigned_at")

        return list(dict.fromkeys(changed_fields))

    def _apply_suggestion(
        self,
        lead: Lead,
        suggestion: LeadAssignmentSuggestion,
        *,
        changed_fields: list[str],
        overwrite: bool,
    ) -> None:
        assignment_rule_value = suggestion.assignment_rule_id
        if not overwrite and lead.assigned_sales_rep_id is not None:
            assignment_rule_value = None

        for field_name, value in [
            ("sales_region_id", suggestion.sales_region_id),
            ("market_segment_id", suggestion.market_segment_id),
            ("market_subsegment_id", suggestion.market_subsegment_id),
            ("assigned_sales_rep_id", suggestion.assigned_sales_rep_id),
            ("assignment_rule_id", assignment_rule_value),
        ]:
            if field_name in changed_fields:
                setattr(lead, field_name, value)

        if "assignment_explanation" in changed_fields:
            lead.assignment_explanation = suggestion.explanation
        if "assignment_metadata_json" in changed_fields:
            lead.assignment_metadata_json = suggestion.metadata
        if "assigned_at" in changed_fields:
            lead.assigned_at = utcnow()

    @staticmethod
    def _state_matches(*, lead_state: str | None, region: SalesRegion) -> bool:
        region_state = normalize_text(region.state)
        return not (region_state and lead_state and region_state != lead_state)

    @staticmethod
    def _normalized_cities(region: SalesRegion) -> set[str]:
        return {
            normalized_city
            for city in region.cities_json or []
            if (normalized_city := normalize_text(city))
        }

    @staticmethod
    def _requires_neighborhood_match(region: SalesRegion) -> bool:
        return bool((region.metadata_json or {}).get("requires_neighborhood_match"))

    def _postal_code_matches(self, lead: Lead, region: SalesRegion) -> bool:
        lead_postal_code = self._digits(lead.postal_code)
        if not lead_postal_code:
            return False

        lead_city = normalize_text(lead.city)
        normalized_cities = self._normalized_cities(region)
        if normalized_cities and lead_city and lead_city not in normalized_cities:
            return False

        for prefix in region.postal_codes_json or []:
            normalized_prefix = self._digits(prefix)
            if normalized_prefix and lead_postal_code.startswith(normalized_prefix):
                return True
        return False

    def _neighborhood_matches(self, lead: Lead, region: SalesRegion) -> bool:
        keywords = (region.metadata_json or {}).get("neighborhood_keywords") or []
        if not keywords:
            return False

        lead_city = normalize_text(lead.city)
        normalized_cities = self._normalized_cities(region)
        if normalized_cities and lead_city and lead_city not in normalized_cities:
            return False

        haystack = normalize_text(" ".join(value for value in [lead.neighborhood, lead.address] if value)) or ""
        if not haystack:
            return False

        return any(
            normalized_keyword in haystack
            for keyword in keywords
            if (normalized_keyword := normalize_text(str(keyword)))
        )

    @staticmethod
    def _digits(value: str | None) -> str:
        return "".join(character for character in str(value or "") if character.isdigit())

    def _match_assignment_rule(
        self,
        *,
        organization_id: int,
        sales_region_id: int | None,
        market_segment_id: int | None,
        market_subsegment_id: int | None,
    ) -> AssignmentRule | None:
        query = (
            select(AssignmentRule)
            .options(
                selectinload(AssignmentRule.sales_rep),
                selectinload(AssignmentRule.sales_region),
                selectinload(AssignmentRule.market_segment),
                selectinload(AssignmentRule.market_subsegment),
            )
            .where(AssignmentRule.organization_id == organization_id, AssignmentRule.is_active.is_(True))
            .order_by(AssignmentRule.priority.asc(), AssignmentRule.id.asc())
        )
        for rule in self.db.execute(query).scalars().all():
            if not rule.sales_rep or not rule.sales_rep.is_active or rule.sales_rep.organization_id != organization_id:
                continue
            if rule.sales_region and rule.sales_region.organization_id != organization_id:
                continue
            if rule.market_segment and rule.market_segment.organization_id != organization_id:
                continue
            if rule.market_subsegment and rule.market_subsegment.organization_id != organization_id:
                continue
            if rule.sales_region_id is not None and rule.sales_region_id != sales_region_id:
                continue
            if rule.market_segment_id is not None and rule.market_segment_id != market_segment_id:
                continue
            if rule.market_subsegment_id is not None and rule.market_subsegment_id != market_subsegment_id:
                continue
            return rule
        return None

    @staticmethod
    def _lead_text(lead: Lead) -> str:
        return normalize_text(
            " ".join(
                value
                for value in [
                    lead.business_name,
                    lead.normalized_business_name,
                    lead.category,
                    lead.website,
                    lead.domain,
                ]
                if value
            )
        ) or ""

    @staticmethod
    def _build_explanation(
        *,
        region: SalesRegion | None,
        subsegment_match: _SubsegmentMatch | None,
        rule: AssignmentRule | None,
    ) -> str:
        parts: list[str] = []
        if region:
            parts.append(f"Matched sales region '{region.name}' from lead geography.")
        else:
            parts.append("No sales region matched.")

        if subsegment_match:
            keywords = ", ".join(subsegment_match.matched_keywords)
            parts.append(f"Matched market subsegment '{subsegment_match.subsegment.name}' using keywords: {keywords}.")
        else:
            parts.append("No market subsegment matched.")

        if rule:
            parts.append(f"Matched assignment rule '{rule.name}' with priority {rule.priority}.")
        else:
            parts.append("No assignment rule matched.")
        return " ".join(parts)

    @staticmethod
    def _build_metadata(
        *,
        region: SalesRegion | None,
        lead: Lead,
        segment: MarketSegment | None,
        subsegment_match: _SubsegmentMatch | None,
        rule: AssignmentRule | None,
    ) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "sales_region": (
                {
                    "id": region.id,
                    "name": region.name,
                    "matched_city": lead.city,
                    "matched_state": lead.state,
                }
                if region
                else None
            ),
            "market_segment": (
                {
                    "id": segment.id,
                    "key": segment.key,
                    "name": segment.name,
                }
                if segment
                else None
            ),
            "market_subsegment": (
                {
                    "id": subsegment_match.subsegment.id,
                    "key": subsegment_match.subsegment.key,
                    "name": subsegment_match.subsegment.name,
                    "matched_keywords": subsegment_match.matched_keywords,
                }
                if subsegment_match
                else None
            ),
            "assignment_rule": (
                {
                    "id": rule.id,
                    "name": rule.name,
                    "priority": rule.priority,
                }
                if rule
                else None
            ),
            "sales_rep": (
                {
                    "id": rule.sales_rep.id,
                    "name": rule.sales_rep.name,
                }
                if rule and rule.sales_rep
                else None
            ),
        }
