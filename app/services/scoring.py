from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.enums import LeadSourceType
from app.models.lead import Lead
from app.repositories.lead_repository import LeadRepository
from app.schemas.lead import LeadListFilters
from app.schemas.scoring import ScoreResult


class ScoringService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = LeadRepository(db)

    def score_lead(self, lead_id: int) -> ScoreResult:
        lead = self.repository.get_with_related(lead_id)
        if lead is None:
            raise ValueError(f"Lead {lead_id} not found.")
        return self.score_lead_instance(lead)

    def score_lead_instance(self, lead: Lead) -> ScoreResult:
        breakdown = self._calculate_breakdown(lead)
        total_score = int(sum(item["points"] for item in breakdown.values()))
        lead.lead_score = max(0, min(100, total_score))
        lead.score_breakdown = breakdown
        self.db.flush()
        return ScoreResult(lead_id=lead.id, lead_score=lead.lead_score, breakdown=breakdown)

    def score_batch(
        self,
        *,
        lead_ids: list[int] | None = None,
        filters: LeadListFilters | None = None,
    ) -> list[ScoreResult]:
        if lead_ids:
            leads = self.repository.get_by_ids(lead_ids)
        else:
            leads = self.repository.list_all_leads(filters)
        results = [self.score_lead_instance(lead) for lead in leads]
        self.db.commit()
        return results

    def _calculate_breakdown(self, lead: Lead) -> dict[str, dict[str, Any]]:
        has_website = bool(lead.website or lead.domain)
        has_map_listing = bool(lead.google_maps_url or lead.google_place_id)
        rating = getattr(lead, "rating", None)
        review_count = getattr(lead, "review_count", None)
        core_field_count = sum(
            1
            for value in [
                lead.business_name,
                lead.category,
                lead.city,
                lead.state,
                lead.address,
                lead.phone,
                lead.website or lead.domain,
                lead.email,
                lead.whatsapp,
                lead.google_maps_url or lead.google_place_id,
            ]
            if value
        )

        breakdown: dict[str, dict[str, Any]] = {
            "has_email": {
                "points": 14 if lead.email else 0,
                "reason": "Public email available." if lead.email else "No public email found yet.",
            },
            "has_phone": {
                "points": 14 if lead.phone else 0,
                "reason": "Phone number available." if lead.phone else "No phone number found yet.",
            },
            "has_whatsapp": {
                "points": 9 if lead.whatsapp else 0,
                "reason": "WhatsApp contact available." if lead.whatsapp else "No WhatsApp contact found yet.",
            },
            "has_website": {
                "points": 12 if has_website else 0,
                "reason": "Business website or domain available." if has_website else "No business website found yet.",
            },
            "has_address": {
                "points": 10 if lead.address else 0,
                "reason": "Street address available." if lead.address else "No street address found yet.",
            },
            "has_map_listing": {
                "points": 8 if has_map_listing else 0,
                "reason": (
                    "Google Maps URL or place id available."
                    if has_map_listing
                    else "No Google Maps URL or place id found yet."
                ),
            },
            "location_completeness": self._location_completeness_breakdown(lead),
            "core_field_completeness": {
                "points": min(8, core_field_count),
                "reason": f"Completed {core_field_count}/10 core discovery fields.",
            },
            "source_reliability": self._source_reliability_breakdown(lead, has_map_listing=has_map_listing),
            "freshness": self._freshness_breakdown(lead),
            "reputation_signals": self._reputation_breakdown(rating=rating, review_count=review_count),
            "not_duplicate": {
                "points": 6 if not lead.is_duplicate else 0,
                "reason": "Lead is canonical." if not lead.is_duplicate else "Lead is marked as duplicate.",
            },
        }
        return breakdown

    @staticmethod
    def _location_completeness_breakdown(lead: Lead) -> dict[str, Any]:
        points = 0
        details: list[str] = []
        if lead.city and lead.state:
            points += 4
            details.append("city/state")
        if lead.postal_code:
            points += 1
            details.append("postal_code")
        if lead.neighborhood:
            points += 1
            details.append("neighborhood")
        return {
            "points": min(6, points),
            "reason": (
                f"Location details available: {', '.join(details)}."
                if details
                else "Only minimal location details are available."
            ),
        }

    @staticmethod
    def _source_reliability_breakdown(lead: Lead, *, has_map_listing: bool) -> dict[str, Any]:
        source_type = lead.lead_source_type
        if source_type == LeadSourceType.GOOGLE_PLACES:
            points = 5 if has_map_listing else 3
            reason = (
                "Discovered from Google Places with a reusable map reference."
                if has_map_listing
                else "Discovered from Google Places without a reusable map reference."
            )
            return {"points": points, "reason": reason}
        if source_type == LeadSourceType.WEBSITE:
            return {"points": 5 if (lead.website or lead.domain) else 3, "reason": "Captured from a public website."}
        if source_type == LeadSourceType.MANUAL_IMPORT:
            return {"points": 4, "reason": "Imported manually from an external source."}
        if source_type == LeadSourceType.MERGED:
            return {"points": 4, "reason": "Merged from existing lead records."}
        if source_type == LeadSourceType.DEMO_SEED:
            return {"points": 1, "reason": "Seeded demo lead with limited source confidence."}
        return {"points": 0, "reason": "No reliable source context available yet."}

    @staticmethod
    def _freshness_breakdown(lead: Lead) -> dict[str, Any]:
        last_checked_at = lead.last_enriched_at
        if last_checked_at is None:
            return {"points": 0, "reason": "No enrichment freshness timestamp is available yet."}
        if last_checked_at.tzinfo is None:
            last_checked_at = last_checked_at.replace(tzinfo=timezone.utc)
        age_days = max(0, (datetime.now(timezone.utc) - last_checked_at).days)
        if age_days <= 30:
            return {"points": 4, "reason": f"Lead data was refreshed within the last {age_days} day(s)."}
        if age_days <= 180:
            return {"points": 2, "reason": f"Lead data was refreshed {age_days} day(s) ago."}
        return {"points": 0, "reason": f"Lead data is stale ({age_days} day(s) since last refresh)."}

    @staticmethod
    def _reputation_breakdown(*, rating: object | None, review_count: object | None) -> dict[str, Any]:
        points = 0
        details: list[str] = []
        if ScoringService._has_positive_number(rating):
            points += 2
            details.append("rating")
        if ScoringService._has_positive_number(review_count):
            points += 2
            details.append("review_count")
        return {
            "points": points,
            "reason": (
                f"Reputation signals available: {', '.join(details)}."
                if details
                else "No rating or review count is tracked on this lead."
            ),
        }

    @staticmethod
    def _has_positive_number(value: object | None) -> bool:
        try:
            return value is not None and float(value) > 0
        except (TypeError, ValueError):
            return False
