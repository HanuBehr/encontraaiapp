from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings
from app.enums import ActivityAction
from app.models.activity_log import ActivityLog
from app.models.base import utcnow
from app.repositories.lead_repository import LeadRepository
from app.schemas.lead import (
    CNPJEnrichmentRunResult,
    LeadBatchCNPJEnrichmentResponse,
    LeadBatchCNPJEnrichmentSummary,
)
from app.services.normalization import (
    normalize_brazilian_state,
    normalize_business_name,
    normalize_domain,
    normalize_phone_br,
    normalize_text,
    split_street_and_number,
)
from app.services.providers.cnpja import (
    CNPJAProvider,
    CNPJAProviderError,
    CNPJANotFoundError,
    CNPJLookupResult,
    MISSING_CNPJA_API_KEY_BATCH_MESSAGE,
    normalize_cnpj,
)


SKIPPED_KNOWN_CNPJ_REASON = "Lead already has a confirmed CNPJ."
MISSING_COMPANY_SEARCH_REASON = "Lead has no known CNPJ and company search is not configured."
INVALID_LEAD_CNPJ_REASON = "Lead has a saved CNPJ that needs review before lookup."
NO_PROVIDER_MATCH_REASON = "No confident CNPJ match found for this lead."
NEEDS_REVIEW_REASON = "Possible CNPJ found, needs review."
OPEN_API_BATCH_LIMIT = 3
HIGH_CONFIDENCE_SCORE = 80
MEDIUM_CONFIDENCE_SCORE = 60
CLEAR_WINNER_GAP = 10


@dataclass(slots=True)
class _PendingLookup:
    lead_id: int
    cnpj: str


@dataclass(slots=True)
class _PendingSearch:
    lead_id: int


@dataclass(slots=True)
class _ScoredCandidate:
    candidate: CNPJLookupResult
    score: int
    evidence: dict[str, int]
    penalties: list[str]
    strong_name_match: bool
    supportive_signal_count: int


class CNPJEnrichmentService:
    def __init__(
        self,
        db: Session,
        settings: Settings,
        *,
        provider: CNPJAProvider | None = None,
    ) -> None:
        self.db = db
        self.settings = settings
        self.repository = LeadRepository(db)
        self.provider = provider or CNPJAProvider(settings)

    def enrich_lead_ids(
        self,
        lead_ids: list[int],
        *,
        force: bool = False,
        actor: str = "system",
        scope_label: str = "lead ids",
    ) -> LeadBatchCNPJEnrichmentResponse:
        requested_ids = [int(lead_id) for lead_id in dict.fromkeys(lead_ids)]
        lead_map = {lead.id: lead for lead in self.repository.get_by_ids(requested_ids)}
        results: list[CNPJEnrichmentRunResult] = []
        errors: list[str] = []
        pending_lookups: list[_PendingLookup] = []
        pending_searches: list[_PendingSearch] = []

        for lead_id in requested_ids:
            lead = lead_map.get(lead_id)
            if lead is None:
                error_message = f"Lead {lead_id} not found."
                results.append(
                    CNPJEnrichmentRunResult(
                        lead_id=lead_id,
                        success=False,
                        match_status="error",
                        error_message=error_message,
                    )
                )
                errors.append(error_message)
                continue

            if not force and lead.cnpj and lead.cnpj_match_status == "matched":
                results.append(
                    CNPJEnrichmentRunResult(
                        lead_id=lead.id,
                        business_name=lead.business_name,
                        success=True,
                        cnpj=lead.cnpj,
                        legal_name=lead.legal_name,
                        match_status="matched",
                        match_confidence=lead.cnpj_match_confidence,
                        skipped_reason=SKIPPED_KNOWN_CNPJ_REASON,
                        last_enriched_at=lead.cnpj_last_enriched_at,
                    )
                )
                continue

            normalized_cnpj = normalize_cnpj(lead.cnpj)
            if normalized_cnpj is not None:
                pending_lookups.append(_PendingLookup(lead_id=lead.id, cnpj=normalized_cnpj))
                continue

            if lead.cnpj:
                self._mark_attempt(
                    lead,
                    actor=actor,
                    match_status="needs_review",
                    match_confidence=None,
                    source_provider=lead.cnpj_source_provider,
                    skipped_reason=INVALID_LEAD_CNPJ_REASON,
                    error_message=None,
                )
                results.append(
                    CNPJEnrichmentRunResult(
                        lead_id=lead.id,
                        business_name=lead.business_name,
                        success=True,
                        cnpj=lead.cnpj,
                        legal_name=lead.legal_name,
                        match_status="needs_review",
                        skipped_reason=INVALID_LEAD_CNPJ_REASON,
                        last_enriched_at=lead.cnpj_last_enriched_at,
                    )
                )
                continue

            pending_searches.append(_PendingSearch(lead_id=lead.id))

        if (
            not self.settings.cnpja_commercial_configured
            and len(pending_lookups) > OPEN_API_BATCH_LIMIT
        ):
            raise CNPJAProviderError(MISSING_CNPJA_API_KEY_BATCH_MESSAGE, status_code=503)

        for search in pending_searches:
            lead = lead_map[search.lead_id]
            results.append(self._enrich_missing_cnpj_lead(lead, actor=actor, errors=errors))

        for lookup in pending_lookups:
            lead = lead_map[lookup.lead_id]
            results.append(self._enrich_known_cnpj_lead(lead, lookup.cnpj, actor=actor, errors=errors))

        summary = self._build_summary(
            requested_ids=requested_ids,
            results=results,
            errors=errors,
            scope_label=scope_label,
        )
        return LeadBatchCNPJEnrichmentResponse(
            processed=len(results),
            results=results,
            summary=summary,
        )

    def _enrich_known_cnpj_lead(
        self,
        lead,
        cnpj: str,
        *,
        actor: str,
        errors: list[str],
    ) -> CNPJEnrichmentRunResult:
        try:
            result = self.provider.lookup_known_cnpj(cnpj)
        except CNPJANotFoundError:
            self._mark_attempt(
                lead,
                actor=actor,
                match_status="not_found",
                match_confidence=None,
                source_provider="cnpja",
                skipped_reason="No provider match found for the saved CNPJ.",
                error_message=None,
            )
            return CNPJEnrichmentRunResult(
                lead_id=lead.id,
                business_name=lead.business_name,
                cnpj=lead.cnpj,
                legal_name=lead.legal_name,
                match_status="not_found",
                skipped_reason="No provider match found for the saved CNPJ.",
                last_enriched_at=lead.cnpj_last_enriched_at,
            )
        except CNPJAProviderError as exc:
            return self._record_error(lead, actor=actor, error_message=str(exc), errors=errors)

        return self._apply_lookup_result(
            lead,
            result,
            actor=actor,
            match_confidence=1.0,
            matched_by="known_cnpj",
            candidate_summary=None,
        )

    def _enrich_missing_cnpj_lead(
        self,
        lead,
        *,
        actor: str,
        errors: list[str],
    ) -> CNPJEnrichmentRunResult:
        if not self.settings.cnpja_company_search_configured:
            self._mark_attempt(
                lead,
                actor=actor,
                match_status="not_found",
                match_confidence=None,
                source_provider=lead.cnpj_source_provider or "cnpja",
                skipped_reason=MISSING_COMPANY_SEARCH_REASON,
                error_message=None,
            )
            return CNPJEnrichmentRunResult(
                lead_id=lead.id,
                business_name=lead.business_name,
                success=True,
                cnpj=None,
                legal_name=lead.legal_name,
                match_status="not_found",
                skipped_reason=MISSING_COMPANY_SEARCH_REASON,
                last_enriched_at=lead.cnpj_last_enriched_at,
            )

        try:
            candidates = self.provider.search_companies(
                business_name=lead.business_name,
                city=lead.city,
                state=lead.state,
                postal_code=lead.postal_code,
                website=lead.website or lead.domain,
                phone=lead.phone,
                whatsapp=lead.whatsapp,
                address=lead.address,
                neighborhood=lead.neighborhood,
            )
        except CNPJAProviderError as exc:
            return self._record_error(lead, actor=actor, error_message=str(exc), errors=errors)

        if not candidates:
            self._mark_attempt(
                lead,
                actor=actor,
                match_status="not_found",
                match_confidence=None,
                source_provider="cnpja_search",
                skipped_reason=NO_PROVIDER_MATCH_REASON,
                error_message=None,
            )
            return CNPJEnrichmentRunResult(
                lead_id=lead.id,
                business_name=lead.business_name,
                success=True,
                cnpj=None,
                legal_name=lead.legal_name,
                match_status="not_found",
                skipped_reason=NO_PROVIDER_MATCH_REASON,
                last_enriched_at=lead.cnpj_last_enriched_at,
            )

        scored_candidates = sorted(
            (self._score_candidate(lead, candidate) for candidate in candidates),
            key=lambda item: item.score,
            reverse=True,
        )
        best_candidate = scored_candidates[0]
        top_gap = (
            best_candidate.score - scored_candidates[1].score
            if len(scored_candidates) > 1
            else CLEAR_WINNER_GAP
        )
        candidate_summary = self._build_candidate_summary(
            best_candidate,
            candidate_count=len(scored_candidates),
        )

        if self._is_high_confidence_match(best_candidate, top_gap=top_gap):
            try:
                confirmed_lookup = self.provider.lookup_known_cnpj(best_candidate.candidate.cnpj)
            except CNPJANotFoundError:
                self._mark_attempt(
                    lead,
                    actor=actor,
                    match_status="not_found",
                    match_confidence=None,
                    source_provider=best_candidate.candidate.source_provider,
                    skipped_reason=NO_PROVIDER_MATCH_REASON,
                    error_message=None,
                    matched_by="company_search",
                    candidate_summary=candidate_summary,
                )
                return CNPJEnrichmentRunResult(
                    lead_id=lead.id,
                    business_name=lead.business_name,
                    success=True,
                    cnpj=None,
                    legal_name=lead.legal_name,
                    match_status="not_found",
                    skipped_reason=NO_PROVIDER_MATCH_REASON,
                    last_enriched_at=lead.cnpj_last_enriched_at,
                )
            except CNPJAProviderError as exc:
                return self._record_error(lead, actor=actor, error_message=str(exc), errors=errors)

            return self._apply_lookup_result(
                lead,
                confirmed_lookup,
                actor=actor,
                match_confidence=self._score_to_confidence(best_candidate.score),
                matched_by="company_search",
                candidate_summary=candidate_summary,
            )

        if best_candidate.score >= MEDIUM_CONFIDENCE_SCORE and not self._has_location_conflict(best_candidate):
            confidence = self._score_to_confidence(best_candidate.score)
            self._mark_attempt(
                lead,
                actor=actor,
                match_status="needs_review",
                match_confidence=confidence,
                source_provider=best_candidate.candidate.source_provider,
                skipped_reason=NEEDS_REVIEW_REASON,
                error_message=None,
                matched_by="company_search",
                candidate_summary=candidate_summary,
            )
            return CNPJEnrichmentRunResult(
                lead_id=lead.id,
                business_name=lead.business_name,
                success=True,
                cnpj=None,
                legal_name=lead.legal_name,
                match_status="needs_review",
                match_confidence=confidence,
                skipped_reason=NEEDS_REVIEW_REASON,
                last_enriched_at=lead.cnpj_last_enriched_at,
            )

        self._mark_attempt(
            lead,
            actor=actor,
            match_status="not_found",
            match_confidence=None,
            source_provider=best_candidate.candidate.source_provider,
            skipped_reason=NO_PROVIDER_MATCH_REASON,
            error_message=None,
            matched_by="company_search",
            candidate_summary=candidate_summary,
        )
        return CNPJEnrichmentRunResult(
            lead_id=lead.id,
            business_name=lead.business_name,
            success=True,
            cnpj=None,
            legal_name=lead.legal_name,
            match_status="not_found",
            skipped_reason=NO_PROVIDER_MATCH_REASON,
            last_enriched_at=lead.cnpj_last_enriched_at,
        )

    def _apply_lookup_result(
        self,
        lead,
        lookup: CNPJLookupResult,
        *,
        actor: str,
        match_confidence: float,
        matched_by: str,
        candidate_summary: dict[str, Any] | None,
    ) -> CNPJEnrichmentRunResult:
        fields_updated: list[str] = []
        if lead.cnpj != lookup.cnpj:
            lead.cnpj = lookup.cnpj
            fields_updated.append("cnpj")
        if lookup.legal_name and lead.legal_name != lookup.legal_name:
            lead.legal_name = lookup.legal_name
            fields_updated.append("legal_name")

        lead.cnpj_match_status = "matched"
        lead.cnpj_match_confidence = match_confidence
        lead.cnpj_last_enriched_at = utcnow()
        lead.cnpj_source_provider = lookup.source_provider
        lead.cnpj_metadata_json = self._build_metadata(
            lead.cnpj_metadata_json,
            lookup=lookup,
            match_status="matched",
            skipped_reason=None,
            error_message=None,
            matched_by=matched_by,
            candidate_summary=candidate_summary,
        )
        fields_updated.extend(
            [
                "cnpj_match_status",
                "cnpj_match_confidence",
                "cnpj_last_enriched_at",
                "cnpj_source_provider",
                "cnpj_metadata_json",
            ]
        )

        self.db.add(
            ActivityLog(
                organization_id=lead.organization_id or self.repository.organization_id,
                lead_id=lead.id,
                entity_type="lead",
                entity_id=lead.id,
                action=ActivityAction.ENRICHED,
                actor=actor,
                message="CNPJ enrichment completed.",
                metadata_json={
                    "enrichment_type": "cnpj",
                    "cnpj": lead.cnpj,
                    "legal_name": lead.legal_name,
                    "match_status": lead.cnpj_match_status,
                    "match_confidence": lead.cnpj_match_confidence,
                    "source_provider": lead.cnpj_source_provider,
                    "provider_metadata": lead.cnpj_metadata_json,
                },
            )
        )
        self.db.commit()
        self.db.refresh(lead)

        return CNPJEnrichmentRunResult(
            lead_id=lead.id,
            business_name=lead.business_name,
            success=True,
            cnpj=lead.cnpj,
            legal_name=lead.legal_name,
            match_status="matched",
            match_confidence=lead.cnpj_match_confidence,
            fields_updated=fields_updated,
            last_enriched_at=lead.cnpj_last_enriched_at,
        )

    def _mark_attempt(
        self,
        lead,
        *,
        actor: str,
        match_status: str,
        match_confidence: float | None,
        source_provider: str | None,
        skipped_reason: str | None,
        error_message: str | None,
        matched_by: str | None = None,
        candidate_summary: dict[str, Any] | None = None,
    ) -> None:
        lead.cnpj_match_status = match_status
        lead.cnpj_match_confidence = match_confidence
        lead.cnpj_last_enriched_at = utcnow()
        if source_provider:
            lead.cnpj_source_provider = source_provider
        lead.cnpj_metadata_json = self._build_metadata(
            lead.cnpj_metadata_json,
            lookup=None,
            match_status=match_status,
            skipped_reason=skipped_reason,
            error_message=error_message,
            matched_by=matched_by,
            candidate_summary=candidate_summary,
        )
        self.db.add(
            ActivityLog(
                organization_id=lead.organization_id or self.repository.organization_id,
                lead_id=lead.id,
                entity_type="lead",
                entity_id=lead.id,
                action=ActivityAction.ENRICHED,
                actor=actor,
                message="CNPJ enrichment attempted.",
                metadata_json={
                    "enrichment_type": "cnpj",
                    "cnpj": lead.cnpj,
                    "legal_name": lead.legal_name,
                    "match_status": lead.cnpj_match_status,
                    "match_confidence": lead.cnpj_match_confidence,
                    "source_provider": lead.cnpj_source_provider,
                    "skipped_reason": skipped_reason,
                    "error_message": error_message,
                    "candidate_summary": candidate_summary,
                },
            )
        )
        self.db.commit()
        self.db.refresh(lead)

    def _record_error(
        self,
        lead,
        *,
        actor: str,
        error_message: str,
        errors: list[str],
    ) -> CNPJEnrichmentRunResult:
        self.db.rollback()
        self._mark_attempt(
            lead,
            actor=actor,
            match_status="error",
            match_confidence=None,
            source_provider=lead.cnpj_source_provider or "cnpja",
            skipped_reason=None,
            error_message=error_message,
        )
        errors.append(f"Lead {lead.id}: {error_message}")
        return CNPJEnrichmentRunResult(
            lead_id=lead.id,
            business_name=lead.business_name,
            success=False,
            cnpj=lead.cnpj,
            legal_name=lead.legal_name,
            match_status="error",
            error_message=error_message,
            last_enriched_at=lead.cnpj_last_enriched_at,
        )

    def _score_candidate(self, lead, candidate: CNPJLookupResult) -> _ScoredCandidate:
        evidence: dict[str, int] = {}
        penalties: list[str] = []
        score = 0

        lead_domain = normalize_domain(lead.website) or normalize_domain(lead.domain)
        candidate_domain = candidate.domain or normalize_domain(candidate.website)
        if lead_domain and candidate_domain and lead_domain == candidate_domain:
            evidence["domain"] = 40
            score += 40

        lead_numbers = {
            value
            for value in (
                normalize_phone_br(lead.phone),
                normalize_phone_br(lead.whatsapp),
            )
            if value
        }
        candidate_numbers = {
            value for value in (normalize_phone_br(phone) for phone in candidate.phones) if value
        }
        if lead_numbers and candidate_numbers and lead_numbers.intersection(candidate_numbers):
            evidence["phone"] = 35
            score += 35

        lead_name = normalize_business_name(lead.business_name)
        candidate_names = {
            value
            for value in (
                normalize_business_name(candidate.trade_name),
                normalize_business_name(candidate.legal_name),
            )
            if value
        }
        strong_name_match = False
        if lead_name and candidate_names:
            if lead_name in candidate_names:
                evidence["name"] = 25
                score += 25
                strong_name_match = True
            elif any(self._is_strong_name_variant(lead_name, candidate_name) for candidate_name in candidate_names):
                evidence["name"] = 15
                score += 15

        lead_street, lead_number = split_street_and_number(
            lead.address,
            neighborhood=lead.neighborhood,
            city=lead.city,
            state=lead.state,
            postal_code=lead.postal_code,
        )
        candidate_street, candidate_number = split_street_and_number(
            candidate.address,
            city=candidate.city,
            state=candidate.state,
            postal_code=candidate.postal_code,
        )
        normalized_lead_street = normalize_text(lead_street)
        normalized_candidate_street = normalize_text(candidate_street)
        if (
            normalized_lead_street
            and normalized_candidate_street
            and normalized_lead_street == normalized_candidate_street
        ):
            evidence["address"] = 20
            score += 20
        if lead_number and candidate_number and lead_number != candidate_number:
            score -= 10
            penalties.append("different_number")

        lead_postal = self._normalize_postal_code(lead.postal_code)
        candidate_postal = self._normalize_postal_code(candidate.postal_code)
        if lead_postal and candidate_postal and lead_postal == candidate_postal:
            evidence["postal_code"] = 15
            score += 15

        lead_city = normalize_text(lead.city)
        candidate_city = normalize_text(candidate.city)
        if lead_city and candidate_city:
            if lead_city == candidate_city:
                evidence["city"] = 10
                score += 10
            else:
                score -= 30
                penalties.append("different_city")

        lead_state = normalize_brazilian_state(lead.state) or normalize_text(lead.state)
        candidate_state = normalize_brazilian_state(candidate.state) or normalize_text(candidate.state)
        if lead_state and candidate_state:
            if lead_state == candidate_state:
                evidence["state"] = 5
                score += 5
            else:
                score -= 35
                penalties.append("different_state")

        supportive_signal_count = sum(
            1 for key in ("domain", "phone", "address", "postal_code") if key in evidence
        )
        return _ScoredCandidate(
            candidate=candidate,
            score=max(score, 0),
            evidence=evidence,
            penalties=penalties,
            strong_name_match=strong_name_match,
            supportive_signal_count=supportive_signal_count,
        )

    @staticmethod
    def _is_strong_name_variant(lead_name: str, candidate_name: str) -> bool:
        if lead_name == candidate_name:
            return True
        shorter, longer = sorted((lead_name, candidate_name), key=len)
        return len(shorter) >= 10 and (shorter in longer or longer in shorter)

    @staticmethod
    def _normalize_postal_code(value: str | None) -> str | None:
        if not value:
            return None
        digits = "".join(character for character in value if character.isdigit())
        return digits or None

    def _is_high_confidence_match(self, candidate: _ScoredCandidate, *, top_gap: int) -> bool:
        has_strong_identity = candidate.strong_name_match or (
            "domain" in candidate.evidence and "phone" in candidate.evidence
        )
        return (
            candidate.score >= HIGH_CONFIDENCE_SCORE
            and top_gap >= CLEAR_WINNER_GAP
            and candidate.supportive_signal_count >= 1
            and has_strong_identity
            and not self._has_location_conflict(candidate)
        )

    @staticmethod
    def _score_to_confidence(score: int) -> float:
        return round(min(score, 100) / 100, 2)

    @staticmethod
    def _has_location_conflict(candidate: _ScoredCandidate) -> bool:
        return any(penalty in {"different_city", "different_state"} for penalty in candidate.penalties)

    @staticmethod
    def _build_candidate_summary(
        candidate: _ScoredCandidate,
        *,
        candidate_count: int,
    ) -> dict[str, Any]:
        return {
            "cnpj": candidate.candidate.cnpj,
            "legal_name": candidate.candidate.legal_name,
            "trade_name": candidate.candidate.trade_name,
            "city": candidate.candidate.city,
            "state": candidate.candidate.state,
            "postal_code": candidate.candidate.postal_code,
            "website": candidate.candidate.website,
            "domain": candidate.candidate.domain,
            "phones": candidate.candidate.phones,
            "score": candidate.score,
            "match_confidence": CNPJEnrichmentService._score_to_confidence(candidate.score),
            "evidence": candidate.evidence,
            "penalties": candidate.penalties,
            "candidate_count": candidate_count,
        }

    @staticmethod
    def _build_metadata(
        current_metadata: dict | None,
        *,
        lookup: CNPJLookupResult | None,
        match_status: str,
        skipped_reason: str | None,
        error_message: str | None,
        matched_by: str | None = None,
        candidate_summary: dict[str, Any] | None = None,
    ) -> dict:
        metadata = dict(current_metadata or {})
        metadata.update(
            {
                "match_status": match_status,
                "skipped_reason": skipped_reason,
                "error_message": error_message,
            }
        )
        if matched_by:
            metadata["matched_by"] = matched_by
        if candidate_summary is not None:
            metadata["candidate_summary"] = candidate_summary
        if lookup is not None:
            metadata.update(
                {
                    "matched_by": matched_by or "known_cnpj",
                    "provider": lookup.source_provider,
                    "provider_record_id": lookup.provider_record_id,
                    "registration_status": lookup.registration_status,
                    "trade_name": lookup.trade_name,
                    "primary_activity": lookup.primary_activity,
                    "city": lookup.city,
                    "state": lookup.state,
                    "postal_code": lookup.postal_code,
                    "website": lookup.website,
                    "domain": lookup.domain,
                    "phones": lookup.phones,
                    "emails": lookup.emails,
                    "address": lookup.address,
                }
            )
            metadata.update(lookup.metadata)
        return metadata

    @staticmethod
    def _build_summary(
        *,
        requested_ids: list[int],
        results: list[CNPJEnrichmentRunResult],
        errors: list[str],
        scope_label: str,
    ) -> LeadBatchCNPJEnrichmentSummary:
        return LeadBatchCNPJEnrichmentSummary(
            scope_label=scope_label,
            requested=len(requested_ids),
            processed=len(results),
            matched_count=sum(
                1
                for item in results
                if item.match_status == "matched" and not item.skipped_reason
            ),
            needs_review_count=sum(1 for item in results if item.match_status == "needs_review"),
            not_found_count=sum(1 for item in results if item.match_status == "not_found"),
            skipped_known_count=sum(
                1 for item in results if item.skipped_reason == SKIPPED_KNOWN_CNPJ_REASON
            ),
            error_count=sum(1 for item in results if not item.success or item.match_status == "error"),
            errors=errors,
        )
