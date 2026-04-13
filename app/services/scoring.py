from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.repositories.lead_repository import LeadRepository
from app.schemas.lead import LeadListFilters
from app.schemas.scoring import ScoreResult
from app.services.normalization import normalize_text


CATEGORY_KEYWORDS = (
    "oficina",
    "mecanica",
    "auto eletrica",
    "auto eletrico",
    "auto center",
    "desmanche",
    "autopeca",
    "autopecas",
    "assistencia tecnica",
    "manutencao",
    "conserto",
    "eletronica",
    "computador",
)


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
        category_text = normalize_text(" ".join(filter(None, [lead.category, lead.business_name]))) or ""
        material_profile = lead.material_profile or {}
        relevant_materials = [name for name, details in material_profile.items() if details.get("relevant")]

        completeness_points = sum(
            1
            for value in [
                lead.address,
                lead.neighborhood,
                lead.postal_code,
                lead.instagram,
                lead.last_enriched_at,
            ]
            if value
        )

        location_points = 0
        if lead.raw_discovery_records:
            location_points = 10
        elif lead.city and lead.state:
            location_points = 6
        elif lead.latitude is not None and lead.longitude is not None:
            location_points = 4

        category_points = 0
        if any(keyword in category_text for keyword in CATEGORY_KEYWORDS):
            category_points = 15
        elif category_text:
            category_points = 7

        material_points = min(15, len(relevant_materials) * 5)

        breakdown: dict[str, dict[str, Any]] = {
            "has_email": {
                "points": 15 if lead.email else 0,
                "reason": "Public email available." if lead.email else "No email found.",
            },
            "has_phone": {
                "points": 10 if lead.phone else 0,
                "reason": "Phone available." if lead.phone else "No phone found.",
            },
            "has_whatsapp": {
                "points": 12 if lead.whatsapp else 0,
                "reason": "WhatsApp available." if lead.whatsapp else "No WhatsApp found.",
            },
            "has_website": {
                "points": 8 if lead.website else 0,
                "reason": "Website available." if lead.website else "No website found.",
            },
            "category_relevance": {
                "points": category_points,
                "reason": f"Category text matched relevant keywords: {lead.category or lead.business_name}" if category_points else "No strong category relevance yet.",
            },
            "material_relevance": {
                "points": material_points,
                "reason": (
                    f"Relevant material signals: {', '.join(relevant_materials)}"
                    if relevant_materials
                    else "No material signals found yet."
                ),
            },
            "location_relevance": {
                "points": location_points,
                "reason": (
                    "Lead was discovered in a tracked search/import context."
                    if lead.raw_discovery_records
                    else "Location present but not tied to discovery context."
                    if location_points
                    else "Weak location context."
                ),
            },
            "not_duplicate": {
                "points": 10 if not lead.is_duplicate else 0,
                "reason": "Lead is canonical." if not lead.is_duplicate else "Lead is marked as duplicate.",
            },
            "data_completeness": {
                "points": min(5, completeness_points),
                "reason": f"Completed {completeness_points}/5 quality fields.",
            },
        }
        return breakdown
