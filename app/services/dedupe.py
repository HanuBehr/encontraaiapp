from __future__ import annotations

from itertools import combinations
from typing import Any

from sqlalchemy.orm import Session

from app.enums import ActivityAction, ContactType, LeadStatus
from app.models.activity_log import ActivityLog
from app.models.lead import Lead
from app.repositories.lead_repository import LeadRepository
from app.schemas.dedupe import (
    DedupeResult,
    DuplicateCandidate,
    DuplicatePreviewResponse,
)
from app.schemas.lead import LeadListFilters, LeadSummary
from app.services.normalization import unique_preserve_order
from app.services.scoring import ScoringService


MATCH_WEIGHTS = {
    "google_place_id": 1.0,
    "phone": 0.9,
    "whatsapp": 0.9,
    "domain": 0.85,
    "normalized_business_name": 0.75,
}


class DedupeService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = LeadRepository(db)
        self.scoring = ScoringService(db)

    def preview_duplicates(
        self,
        *,
        filters: LeadListFilters | None = None,
        lead_ids: list[int] | None = None,
    ) -> DuplicatePreviewResponse:
        leads = self._load_candidates(filters=filters, lead_ids=lead_ids)
        pairs = self._find_duplicate_pairs(leads)
        items = [
            DuplicateCandidate(
                lead_a=LeadSummary.model_validate(pair["lead_a"]),
                lead_b=LeadSummary.model_validate(pair["lead_b"]),
                reasons=pair["reasons"],
                confidence=pair["confidence"],
                recommended_canonical_id=pair["recommended_canonical_id"],
            )
            for pair in pairs
        ]
        return DuplicatePreviewResponse(total_candidates=len(items), items=items)

    def dedupe_pair(
        self,
        *,
        lead_a_id: int,
        lead_b_id: int,
        canonical_lead_id: int | None = None,
        actor: str = "system",
    ) -> DedupeResult:
        lead_a = self.repository.get_with_related(lead_a_id)
        lead_b = self.repository.get_with_related(lead_b_id)
        if lead_a is None or lead_b is None:
            raise ValueError("Both leads must exist for dedupe.")
        if lead_a.id == lead_b.id:
            raise ValueError("Cannot dedupe a lead against itself.")

        reasons = self._pair_reasons(lead_a, lead_b)
        if not reasons:
            raise ValueError("The provided leads do not meet duplicate criteria.")

        resolved_canonical_id = canonical_lead_id or self._choose_canonical(lead_a, lead_b).id
        if resolved_canonical_id not in {lead_a.id, lead_b.id}:
            raise ValueError("canonical_lead_id must match one of the provided leads.")
        canonical = lead_a if lead_a.id == resolved_canonical_id else lead_b
        duplicate = lead_b if canonical is lead_a else lead_a

        if canonical.is_duplicate and canonical.duplicate_of_lead_id:
            canonical = self.repository.get_with_related(canonical.duplicate_of_lead_id) or canonical
        if duplicate.is_duplicate and duplicate.duplicate_of_lead_id == canonical.id:
            return DedupeResult(
                canonical_lead_id=canonical.id,
                duplicate_lead_id=duplicate.id,
                duplicate_reason=duplicate.duplicate_reason or ", ".join(reasons),
                merged_fields=[],
            )

        merged_fields = self._merge_leads(canonical, duplicate)
        duplicate.is_duplicate = True
        duplicate.duplicate_of_lead_id = canonical.id
        duplicate.duplicate_reason = ", ".join(reasons)

        if duplicate.do_not_contact and not canonical.do_not_contact:
            canonical.do_not_contact = True
            merged_fields.append("do_not_contact")
        if canonical.do_not_contact and canonical.status != LeadStatus.DO_NOT_CONTACT:
            canonical.status = LeadStatus.DO_NOT_CONTACT
            merged_fields.append("status")

        self.scoring.score_lead_instance(canonical)
        self.scoring.score_lead_instance(duplicate)

        duplicate_reason = ", ".join(reasons)
        self.db.add(
            ActivityLog(
                organization_id=canonical.organization_id or self.repository.organization_id,
                lead_id=canonical.id,
                entity_type="lead",
                entity_id=canonical.id,
                action=ActivityAction.DEDUPED,
                actor=actor,
                message=f"Lead {duplicate.id} merged into canonical lead {canonical.id}.",
                metadata_json={
                    "duplicate_lead_id": duplicate.id,
                    "duplicate_reason": duplicate_reason,
                    "merged_fields": unique_preserve_order(merged_fields),
                },
            )
        )
        self.db.add(
            ActivityLog(
                organization_id=duplicate.organization_id or self.repository.organization_id,
                lead_id=duplicate.id,
                entity_type="lead",
                entity_id=duplicate.id,
                action=ActivityAction.DEDUPED,
                actor=actor,
                message=f"Lead marked as duplicate of {canonical.id}.",
                metadata_json={
                    "canonical_lead_id": canonical.id,
                    "duplicate_reason": duplicate_reason,
                },
            )
        )
        self.db.commit()

        return DedupeResult(
            canonical_lead_id=canonical.id,
            duplicate_lead_id=duplicate.id,
            duplicate_reason=duplicate_reason,
            merged_fields=unique_preserve_order(merged_fields),
        )

    def dedupe_batch(
        self,
        *,
        filters: LeadListFilters | None = None,
        lead_ids: list[int] | None = None,
        actor: str = "system",
    ) -> list[DedupeResult]:
        preview = self.preview_duplicates(filters=filters, lead_ids=lead_ids)
        results: list[DedupeResult] = []
        seen_duplicates: set[tuple[int, int]] = set()

        for candidate in preview.items:
            pair_key = tuple(sorted([candidate.lead_a.id, candidate.lead_b.id]))
            if pair_key in seen_duplicates:
                continue
            result = self.dedupe_pair(
                lead_a_id=candidate.lead_a.id,
                lead_b_id=candidate.lead_b.id,
                canonical_lead_id=candidate.recommended_canonical_id,
                actor=actor,
            )
            seen_duplicates.add(pair_key)
            results.append(result)

        return results

    def _load_candidates(
        self,
        *,
        filters: LeadListFilters | None = None,
        lead_ids: list[int] | None = None,
    ) -> list[Lead]:
        if lead_ids:
            leads = self.repository.get_by_ids(lead_ids)
        else:
            leads = self.repository.list_all_leads(filters)
        return [lead for lead in leads if not lead.is_duplicate]

    def _find_duplicate_pairs(self, leads: list[Lead]) -> list[dict[str, Any]]:
        pair_payloads: list[dict[str, Any]] = []
        for lead_a, lead_b in combinations(leads, 2):
            reasons = self._pair_reasons(lead_a, lead_b)
            if not reasons:
                continue
            confidence = round(sum(MATCH_WEIGHTS.get(reason, 0.2) for reason in reasons) / max(len(reasons), 1), 2)
            pair_payloads.append(
                {
                    "lead_a": lead_a,
                    "lead_b": lead_b,
                    "reasons": reasons,
                    "confidence": confidence,
                    "recommended_canonical_id": self._choose_canonical(lead_a, lead_b).id,
                }
            )
        pair_payloads.sort(key=lambda item: (item["confidence"], len(item["reasons"])), reverse=True)
        return pair_payloads

    def _pair_reasons(self, lead_a: Lead, lead_b: Lead) -> list[str]:
        reasons: list[str] = []
        if lead_a.google_place_id and lead_a.google_place_id == lead_b.google_place_id:
            reasons.append("google_place_id")
        if lead_a.phone and lead_a.phone == lead_b.phone:
            reasons.append("phone")
        if lead_a.whatsapp and lead_a.whatsapp == lead_b.whatsapp:
            reasons.append("whatsapp")
        if lead_a.domain and lead_a.domain == lead_b.domain:
            reasons.append("domain")
        if (
            lead_a.normalized_business_name
            and lead_a.normalized_business_name == lead_b.normalized_business_name
        ):
            reasons.append("normalized_business_name")

        has_name_with_signal = "normalized_business_name" in reasons and any(
            signal in reasons for signal in ("phone", "whatsapp", "domain")
        )
        if "google_place_id" in reasons or len(reasons) >= 2 or has_name_with_signal:
            return unique_preserve_order(reasons)
        return []

    def _choose_canonical(self, lead_a: Lead, lead_b: Lead) -> Lead:
        score_a = self._canonical_priority(lead_a)
        score_b = self._canonical_priority(lead_b)
        return lead_a if score_a >= score_b else lead_b

    def _canonical_priority(self, lead: Lead) -> float:
        populated_fields = sum(
            1
            for value in [
                lead.email,
                lead.phone,
                lead.whatsapp,
                lead.website,
                lead.address,
                lead.category,
                lead.city,
                lead.domain,
                lead.last_enriched_at,
            ]
            if value
        )
        contact_confidence = sum(contact.confidence for contact in lead.contacts)
        return float(lead.lead_score + (populated_fields * 3) + contact_confidence)

    def _merge_leads(self, canonical: Lead, duplicate: Lead) -> list[str]:
        merged_fields: list[str] = []

        merged_fields.extend(self._copy_canonical_contact_fields(canonical, duplicate))

        for contact in duplicate.contacts:
            copied = self.repository.copy_contact_to_lead(
                contact,
                target_lead_id=canonical.id,
                note_suffix=f"Merged from lead {duplicate.id}.",
            )
            if copied is not None:
                merged_fields.append(f"contact:{contact.contact_type.value}")

        merged_fields.extend(self.repository.sync_canonical_contacts(canonical))

        for field_name in [
            "category",
            "address",
            "neighborhood",
            "city",
            "state",
            "postal_code",
            "latitude",
            "longitude",
            "website",
            "domain",
            "instagram",
            "google_maps_url",
            "google_place_id",
            "source_provider",
            "source_url",
            "owner",
        ]:
            merged = self._merge_scalar_field(canonical, duplicate, field_name)
            if merged:
                merged_fields.append(field_name)

        if duplicate.material_profile:
            merged_profile = self._merge_material_profile(canonical.material_profile or {}, duplicate.material_profile)
            if merged_profile != (canonical.material_profile or {}):
                canonical.material_profile = merged_profile
                merged_fields.append("material_profile")

        if duplicate.tags:
            merged_tags = unique_preserve_order((canonical.tags or []) + (duplicate.tags or []))
            if merged_tags != (canonical.tags or []):
                canonical.tags = merged_tags
                merged_fields.append("tags")

        if duplicate.notes:
            if not canonical.notes:
                canonical.notes = duplicate.notes
                merged_fields.append("notes")
            elif duplicate.notes not in canonical.notes:
                canonical.notes = f"{canonical.notes}\n\n[Merged from lead {duplicate.id}]\n{duplicate.notes}"
                merged_fields.append("notes")

        if duplicate.follow_up_date and (
            canonical.follow_up_date is None or duplicate.follow_up_date < canonical.follow_up_date
        ):
            canonical.follow_up_date = duplicate.follow_up_date
            merged_fields.append("follow_up_date")

        if duplicate.last_contacted_at and (
            canonical.last_contacted_at is None or duplicate.last_contacted_at > canonical.last_contacted_at
        ):
            canonical.last_contacted_at = duplicate.last_contacted_at
            merged_fields.append("last_contacted_at")

        if duplicate.last_enriched_at and (
            canonical.last_enriched_at is None or duplicate.last_enriched_at > canonical.last_enriched_at
        ):
            canonical.last_enriched_at = duplicate.last_enriched_at
            merged_fields.append("last_enriched_at")

        return unique_preserve_order(merged_fields)

    @staticmethod
    def _merge_scalar_field(canonical: Lead, duplicate: Lead, field_name: str) -> bool:
        canonical_value = getattr(canonical, field_name)
        duplicate_value = getattr(duplicate, field_name)
        if canonical_value in (None, "", [], {}) and duplicate_value not in (None, "", [], {}):
            setattr(canonical, field_name, duplicate_value)
            return True
        return False

    @staticmethod
    def _merge_material_profile(current: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
        merged = dict(current)
        for key, value in incoming.items():
            existing = merged.get(key)
            if not existing:
                merged[key] = value
                continue
            merged[key] = {
                "relevant": bool(existing.get("relevant", False) or value.get("relevant", False)),
                "confidence": max(float(existing.get("confidence", 0.0)), float(value.get("confidence", 0.0))),
                "matched_keywords": unique_preserve_order(
                    list(existing.get("matched_keywords", [])) + list(value.get("matched_keywords", []))
                ),
            }
        return merged

    def _copy_canonical_contact_fields(self, canonical: Lead, duplicate: Lead) -> list[str]:
        merged_fields: list[str] = []
        contact_fields = {
            "email": ContactType.EMAIL,
            "phone": ContactType.PHONE,
            "whatsapp": ContactType.WHATSAPP,
            "instagram": ContactType.INSTAGRAM,
        }
        for field_name, contact_type in contact_fields.items():
            duplicate_value = getattr(duplicate, field_name)
            if not duplicate_value:
                continue
            copied = self.repository.add_contact_if_missing(
                lead_id=canonical.id,
                contact_type=contact_type,
                raw_value=duplicate_value,
                normalized_value=duplicate_value,
                source_url=duplicate.source_url,
                source_kind="merged_lead",
                source_record_type="lead",
                source_record_id=duplicate.id,
                confidence=0.6,
                label=f"merged_{field_name}",
                note=f"Merged from canonical field on lead {duplicate.id}.",
            )
            if copied is not None:
                merged_fields.append(field_name)
        return merged_fields
