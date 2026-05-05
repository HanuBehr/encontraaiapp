from __future__ import annotations

from dataclasses import dataclass
import re
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
from app.services.enrichment import EnrichmentService
from app.services.normalization import (
    normalize_brazilian_state,
    normalize_business_name,
    normalize_domain,
    unique_preserve_order,
    normalize_phone_br,
    normalize_text,
    split_street_and_number,
)
from app.services.providers.cnpja import (
    CNPJAProvider,
    CNPJAProviderError,
    CNPJANotFoundError,
    CNPJLookupResult,
    normalize_cnpj,
)


SKIPPED_KNOWN_CNPJ_REASON = "Lead already has a confirmed CNPJ."
INVALID_LEAD_CNPJ_REASON = "Lead has a saved CNPJ that needs review before lookup."
NO_PROVIDER_MATCH_REASON = "No confident CNPJ match found for this lead."
NEEDS_REVIEW_REASON = "Possible CNPJ found, needs review."
NO_WEBSITE_CNPJ_REASON = "No CNPJ was found on the public website."
NO_WEBSITE_AVAILABLE_REASON = "Lead has no public website available for CNPJ inspection."
WEBSITE_UNREACHABLE_REASON = "Public website could not be reached for CNPJ inspection."
WEBSITE_TIMEOUT_REASON = "Public website was too slow for CNPJ inspection."
VALIDATION_FAILED_REASON = "A CNPJ was found on the website, but public validation did not confirm it."
LOW_CONFIDENCE_REASON = "A possible CNPJ was found, but confidence was too low to fill automatically."
MISSING_LEAD_CNPJ_REASON = "CNPJ ausente no lead. APIs públicas consultam apenas CNPJs já conhecidos."
WEBSITE_BATCH_LIMIT_MESSAGE = (
    "Website-based CNPJ enrichment works better in smaller batches. Select fewer leads and retry."
)
OPEN_API_BATCH_LIMIT = 3
CNPJA_OPEN_PUBLIC_BATCH_LIMIT_MESSAGE = (
    "CNPJA open lookup supports at most 3 known-CNPJ lookups per minute. Reduce the batch size or retry later."
)
CNPJ_WS_PUBLIC_BATCH_LIMIT_MESSAGE = (
    "CNPJ.ws public API supports at most 3 known-CNPJ lookups per minute. Reduce the batch size or retry later."
)
HIGH_CONFIDENCE_SCORE = 80
MEDIUM_CONFIDENCE_SCORE = 60
CLEAR_WINNER_GAP = 10
MAX_WEBSITE_CNPJ_CANDIDATES = 3
MAX_WEBSITE_FALLBACK_BATCH = 10
_CNPJ_PATTERN = re.compile(r"(?<!\d)(?:\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}|\d{14})(?!\d)")

REASON_ALREADY_MATCHED = "already_matched"
REASON_SKIPPED_NO_WEBSITE = "skipped_no_website"
REASON_NO_CNPJ_ON_WEBSITE = "no_cnpj_on_website"
REASON_WEBSITE_UNREACHABLE = "website_unreachable"
REASON_WEBSITE_TIMEOUT = "website_timeout"
REASON_CNPJ_VALIDATION_FAILED = "cnpj_validation_failed"
REASON_CNPJ_PROVIDER_RATE_LIMITED = "cnpj_provider_rate_limited"
REASON_LOW_CONFIDENCE = "low_confidence"
REASON_NEEDS_REVIEW = "needs_review"
REASON_MATCHED = "matched"
REASON_PROVIDER_ERROR = "provider_error"
REASON_COMPANY_SEARCH_NOT_CONFIGURED = "company_search_not_configured"
REASON_COMPANY_SEARCH_NO_CANDIDATES = "company_search_no_candidates"
REASON_CNPJA_ZERO_CANDIDATES = "cnpja_zero_candidates"
REASON_COMPANY_SEARCH_LOW_CONFIDENCE = "company_search_low_confidence"
REASON_COMPANY_SEARCH_NEEDS_REVIEW = "company_search_needs_review"
REASON_COMPANY_SEARCH_MATCHED = "company_search_matched"
REASON_COMPANY_SEARCH_PROVIDER_ERROR = "company_search_provider_error"
REASON_COMPANY_SEARCH_RATE_LIMITED = "company_search_rate_limited"
REASON_COMPANY_SEARCH_PREVIEW_ONLY = "company_search_preview_only"
REASON_COMPANY_SEARCH_PENDING_RETRY = "company_search_pending_retry"

COMPANY_SEARCH_NOT_CONFIGURED_REASON = "Paid company search is not configured for this environment."
COMPANY_SEARCH_NO_CANDIDATES_REASON = "No paid company-search candidates were found for this lead."
CNPJA_ZERO_CANDIDATES_REASON = "CNPJá returned zero company-search candidates for this lead."
COMPANY_SEARCH_LOW_CONFIDENCE_REASON = (
    "Paid company search found candidates, but confidence was too low to fill automatically."
)
COMPANY_SEARCH_PROVIDER_ERROR_REASON = "Paid company search failed temporarily."
COMPANY_SEARCH_RATE_LIMIT_RETRY_REASON = (
    "Busca CNPJ limitada pelo provedor. Aguarde cerca de 1 minuto e tente novamente."
)


@dataclass(slots=True)
class _PendingLookup:
    lead_id: int
    cnpj: str


@dataclass(slots=True)
class _PendingSearch:
    lead_id: int


@dataclass(slots=True)
class _WebsiteCNPJCandidate:
    cnpj: str
    source_urls: list[str]
    page_types: list[str]


@dataclass(slots=True)
class _ScoredCandidate:
    candidate: CNPJLookupResult
    score: int
    evidence: dict[str, int]
    penalties: list[str]
    strong_name_match: bool
    supportive_signal_count: int
    source_urls: list[str]
    page_types: list[str]
    matched_by: str


@dataclass(slots=True)
class _LookupCacheEntry:
    result: CNPJLookupResult | None = None
    not_found: bool = False
    error_message: str | None = None


@dataclass(slots=True)
class _WebsiteExtractionCacheEntry:
    candidates: list[_WebsiteCNPJCandidate]
    reason_code: str | None
    skipped_reason: str | None
    attempt_metadata: dict[str, Any]


@dataclass(slots=True)
class _WebsiteEvaluationOutcome:
    final_result: CNPJEnrichmentRunResult | None = None
    can_continue: bool = False
    fallback_reason_code: str | None = None
    fallback_skipped_reason: str | None = None
    attempt_metadata: dict[str, Any] | None = None


def is_valid_cnpj(cnpj: str | None) -> bool:
    normalized = normalize_cnpj(cnpj)
    if normalized is None or len(set(normalized)) == 1:
        return False

    digits = [int(character) for character in normalized]
    first_weights = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    second_weights = [6, *first_weights]

    first_sum = sum(digit * weight for digit, weight in zip(digits[:12], first_weights, strict=False))
    first_check = 0 if first_sum % 11 < 2 else 11 - (first_sum % 11)
    if digits[12] != first_check:
        return False

    second_sum = sum(digit * weight for digit, weight in zip(digits[:13], second_weights, strict=False))
    second_check = 0 if second_sum % 11 < 2 else 11 - (second_sum % 11)
    return digits[13] == second_check


def extract_cnpj_candidates_from_text(text: str | None) -> list[str]:
    if not text:
        return []

    candidates: list[str] = []
    for match in _CNPJ_PATTERN.finditer(text):
        normalized = normalize_cnpj(match.group(0))
        if normalized is None or not is_valid_cnpj(normalized):
            continue
        candidates.append(normalized)
    return unique_preserve_order(candidates)


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
        self._lookup_cache: dict[str, _LookupCacheEntry] = {}
        self._website_candidate_cache: dict[str, _WebsiteExtractionCacheEntry] = {}
        self._company_search_attempts_in_batch = 0
        self._company_search_rate_limited_in_batch = False
        self.enrichment_service = EnrichmentService(
            db,
            settings,
            http_session=getattr(self.provider, "http", None),
        )

    def enrich_lead_ids(
        self,
        lead_ids: list[int],
        *,
        force: bool = False,
        actor: str = "system",
        scope_label: str = "lead ids",
    ) -> LeadBatchCNPJEnrichmentResponse:
        requested_ids = [int(lead_id) for lead_id in dict.fromkeys(lead_ids)]
        self._lookup_cache = {}
        self._website_candidate_cache = {}
        self._company_search_attempts_in_batch = 0
        self._company_search_rate_limited_in_batch = False
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
                        reason_code=REASON_ALREADY_MATCHED,
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
                    reason_code=REASON_NEEDS_REVIEW,
                )
                results.append(
                    CNPJEnrichmentRunResult(
                        lead_id=lead.id,
                        business_name=lead.business_name,
                        success=True,
                        cnpj=lead.cnpj,
                        legal_name=lead.legal_name,
                        match_status="needs_review",
                        reason_code=REASON_NEEDS_REVIEW,
                        skipped_reason=INVALID_LEAD_CNPJ_REASON,
                        last_enriched_at=lead.cnpj_last_enriched_at,
                    )
                )
                continue

            pending_searches.append(_PendingSearch(lead_id=lead.id))

        batch_limit_error = self._get_public_lookup_batch_limit_error(len(pending_lookups))
        if batch_limit_error is not None:
            raise batch_limit_error
        website_pending_count = sum(
            1
            for search in pending_searches
            if (lead_map[search.lead_id].website or lead_map[search.lead_id].domain)
        )
        website_batch_error = self._get_website_batch_limit_error(website_pending_count)
        if website_batch_error is not None:
            raise website_batch_error

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
            result = self._lookup_known_cnpj_cached(cnpj)
        except CNPJANotFoundError:
            self._mark_attempt(
                lead,
                actor=actor,
                match_status="not_found",
                match_confidence=None,
                source_provider=self.settings.cnpj_lookup_provider,
                skipped_reason="No provider match found for the saved CNPJ.",
                error_message=None,
                reason_code=REASON_CNPJ_VALIDATION_FAILED,
            )
            return CNPJEnrichmentRunResult(
                lead_id=lead.id,
                business_name=lead.business_name,
                cnpj=lead.cnpj,
                legal_name=lead.legal_name,
                match_status="not_found",
                reason_code=REASON_CNPJ_VALIDATION_FAILED,
                skipped_reason="No provider match found for the saved CNPJ.",
                last_enriched_at=lead.cnpj_last_enriched_at,
            )
        except CNPJAProviderError as exc:
            return self._record_error(
                lead,
                actor=actor,
                error_message=str(exc),
                errors=errors,
                source_provider=self.settings.cnpj_lookup_provider,
                reason_code=self._provider_reason_code(str(exc)),
            )

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
        website_outcome = self._evaluate_website_cnpj_candidates(lead, actor=actor, errors=errors)
        if website_outcome.final_result is not None:
            return website_outcome.final_result

        if self.settings.cnpj_company_search_requested:
            if not self.settings.cnpj_company_search_configured:
                return self._finalize_missing_cnpj_result(
                    lead,
                    actor=actor,
                    source_provider=self._company_search_source_provider(),
                    reason_code=REASON_COMPANY_SEARCH_NOT_CONFIGURED,
                    skipped_reason=COMPANY_SEARCH_NOT_CONFIGURED_REASON,
                    attempt_metadata=website_outcome.attempt_metadata,
                )
            pending_retry_result = self._maybe_defer_company_search_for_batch(
                lead,
                actor=actor,
                attempt_metadata=website_outcome.attempt_metadata,
            )
            if pending_retry_result is not None:
                return pending_retry_result
            return self._enrich_missing_cnpj_via_company_search(
                lead,
                actor=actor,
                errors=errors,
                attempt_metadata=website_outcome.attempt_metadata,
            )

        return self._finalize_missing_cnpj_result(
            lead,
            actor=actor,
            source_provider=lead.cnpj_source_provider or self.settings.cnpj_lookup_provider,
            reason_code=website_outcome.fallback_reason_code
            or (REASON_NO_CNPJ_ON_WEBSITE if lead.website or lead.domain else REASON_SKIPPED_NO_WEBSITE),
            skipped_reason=website_outcome.fallback_skipped_reason
            or (NO_WEBSITE_CNPJ_REASON if lead.website or lead.domain else NO_WEBSITE_AVAILABLE_REASON),
            attempt_metadata=website_outcome.attempt_metadata,
        )

    def _enrich_missing_cnpj_via_company_search(
        self,
        lead,
        *,
        actor: str,
        errors: list[str],
        attempt_metadata: dict[str, Any] | None,
    ) -> CNPJEnrichmentRunResult:
        provider_attempt_metadata: dict[str, Any] | None = None
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
            provider_attempt_metadata = getattr(self.provider, "last_company_search_metadata", None)
        except CNPJAProviderError as exc:
            provider_attempt_metadata = getattr(self.provider, "last_company_search_metadata", None)
            reason_code = self._provider_reason_code(str(exc), company_search=True)
            if (
                reason_code == REASON_COMPANY_SEARCH_RATE_LIMITED
                and self._uses_cnpja_commercial_company_search()
                and self.settings.cnpja_stop_batch_on_rate_limit
            ):
                self._company_search_rate_limited_in_batch = True
            return self._record_error(
                lead,
                actor=actor,
                error_message=str(exc),
                errors=errors,
                source_provider=self._company_search_source_provider(),
                reason_code=reason_code,
                attempt_metadata=self._merge_attempt_metadata(
                    attempt_metadata,
                    provider_attempt_metadata,
                ),
            )

        merged_attempt_metadata = self._merge_attempt_metadata(
            attempt_metadata,
            provider_attempt_metadata,
        )
        if not candidates:
            return self._finalize_missing_cnpj_result(
                lead,
                actor=actor,
                source_provider=self._company_search_source_provider(),
                reason_code=(
                    REASON_CNPJA_ZERO_CANDIDATES
                    if self._is_cnpja_zero_candidates(provider_attempt_metadata)
                    else REASON_COMPANY_SEARCH_NO_CANDIDATES
                ),
                skipped_reason=(
                    CNPJA_ZERO_CANDIDATES_REASON
                    if self._is_cnpja_zero_candidates(provider_attempt_metadata)
                    else COMPANY_SEARCH_NO_CANDIDATES_REASON
                ),
                attempt_metadata=merged_attempt_metadata,
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

        if self._is_high_confidence_match(best_candidate, top_gap=top_gap) and self._candidate_has_confirmable_cnpj(
            best_candidate
        ):
            return self._apply_lookup_result(
                lead,
                best_candidate.candidate,
                actor=actor,
                match_confidence=self._score_to_confidence(best_candidate.score),
                matched_by="company_search",
                candidate_summary=candidate_summary,
                attempt_metadata=merged_attempt_metadata,
                reason_code=REASON_COMPANY_SEARCH_MATCHED,
            )

        if self._candidate_requires_preview_review(best_candidate):
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
                reason_code=REASON_COMPANY_SEARCH_PREVIEW_ONLY,
                attempt_metadata=merged_attempt_metadata,
            )
            return CNPJEnrichmentRunResult(
                lead_id=lead.id,
                business_name=lead.business_name,
                success=True,
                cnpj=None,
                legal_name=lead.legal_name,
                match_status="needs_review",
                match_confidence=confidence,
                reason_code=REASON_COMPANY_SEARCH_PREVIEW_ONLY,
                skipped_reason=NEEDS_REVIEW_REASON,
                last_enriched_at=lead.cnpj_last_enriched_at,
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
                reason_code=REASON_COMPANY_SEARCH_NEEDS_REVIEW,
                attempt_metadata=merged_attempt_metadata,
            )
            return CNPJEnrichmentRunResult(
                lead_id=lead.id,
                business_name=lead.business_name,
                success=True,
                cnpj=None,
                legal_name=lead.legal_name,
                match_status="needs_review",
                match_confidence=confidence,
                reason_code=REASON_COMPANY_SEARCH_NEEDS_REVIEW,
                skipped_reason=NEEDS_REVIEW_REASON,
                last_enriched_at=lead.cnpj_last_enriched_at,
            )

        return self._finalize_missing_cnpj_result(
            lead,
            actor=actor,
            source_provider=best_candidate.candidate.source_provider,
            reason_code=REASON_COMPANY_SEARCH_LOW_CONFIDENCE,
            skipped_reason=COMPANY_SEARCH_LOW_CONFIDENCE_REASON,
            matched_by="company_search",
            candidate_summary=candidate_summary,
            attempt_metadata=merged_attempt_metadata,
        )

    def _evaluate_website_cnpj_candidates(
        self,
        lead,
        *,
        actor: str,
        errors: list[str],
    ) -> _WebsiteEvaluationOutcome:
        website_url = lead.website or lead.domain
        if not website_url:
            return _WebsiteEvaluationOutcome(
                can_continue=True,
                fallback_reason_code=REASON_SKIPPED_NO_WEBSITE,
                fallback_skipped_reason=NO_WEBSITE_AVAILABLE_REASON,
            )

        extraction = self._get_website_extraction(website_url)
        extracted_candidates = extraction.candidates
        if not extracted_candidates:
            return _WebsiteEvaluationOutcome(
                can_continue=True,
                fallback_reason_code=extraction.reason_code or REASON_NO_CNPJ_ON_WEBSITE,
                fallback_skipped_reason=extraction.skipped_reason or NO_WEBSITE_CNPJ_REASON,
                attempt_metadata=extraction.attempt_metadata,
            )

        validated_candidates: list[_ScoredCandidate] = []
        for extracted_candidate in extracted_candidates[:MAX_WEBSITE_CNPJ_CANDIDATES]:
            try:
                lookup = self._lookup_known_cnpj_cached(extracted_candidate.cnpj)
            except CNPJANotFoundError:
                continue
            except CNPJAProviderError as exc:
                return _WebsiteEvaluationOutcome(
                    final_result=self._record_error(
                        lead,
                        actor=actor,
                        error_message=str(exc),
                        errors=errors,
                        source_provider=self.settings.cnpj_lookup_provider,
                        reason_code=self._provider_reason_code(str(exc)),
                    ),
                    attempt_metadata=extraction.attempt_metadata,
                )

            validated_candidates.append(self._score_website_candidate(lead, lookup, extracted_candidate))

        if not validated_candidates:
            return _WebsiteEvaluationOutcome(
                can_continue=True,
                fallback_reason_code=REASON_CNPJ_VALIDATION_FAILED,
                fallback_skipped_reason=VALIDATION_FAILED_REASON,
                attempt_metadata=extraction.attempt_metadata,
            )

        validated_candidates.sort(key=lambda item: item.score, reverse=True)
        best_candidate = validated_candidates[0]
        top_gap = (
            best_candidate.score - validated_candidates[1].score
            if len(validated_candidates) > 1
            else CLEAR_WINNER_GAP
        )
        candidate_summary = self._build_candidate_summary(
            best_candidate,
            candidate_count=len(validated_candidates),
        )

        if self._is_high_confidence_match(best_candidate, top_gap=top_gap):
            return _WebsiteEvaluationOutcome(
                final_result=self._apply_lookup_result(
                    lead,
                    best_candidate.candidate,
                    actor=actor,
                    match_confidence=self._score_to_confidence(best_candidate.score),
                    matched_by="website_cnpj",
                    candidate_summary=candidate_summary,
                    attempt_metadata=extraction.attempt_metadata,
                ),
                attempt_metadata=extraction.attempt_metadata,
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
                matched_by="website_cnpj",
                candidate_summary=candidate_summary,
                reason_code=REASON_NEEDS_REVIEW,
                attempt_metadata=extraction.attempt_metadata,
            )
            return _WebsiteEvaluationOutcome(
                final_result=CNPJEnrichmentRunResult(
                    lead_id=lead.id,
                    business_name=lead.business_name,
                    success=True,
                    cnpj=None,
                    legal_name=lead.legal_name,
                    match_status="needs_review",
                    match_confidence=confidence,
                    reason_code=REASON_NEEDS_REVIEW,
                    skipped_reason=NEEDS_REVIEW_REASON,
                    last_enriched_at=lead.cnpj_last_enriched_at,
                ),
                attempt_metadata=extraction.attempt_metadata,
            )

        return _WebsiteEvaluationOutcome(
            can_continue=True,
            fallback_reason_code=REASON_LOW_CONFIDENCE,
            fallback_skipped_reason=NO_PROVIDER_MATCH_REASON,
            attempt_metadata={
                **(extraction.attempt_metadata or {}),
                "candidate_summary": candidate_summary,
            },
        )

    def _get_website_extraction(self, website_url: str) -> _WebsiteExtractionCacheEntry:
        cache_key = normalize_domain(website_url) or website_url.strip().lower()
        cached = self._website_candidate_cache.get(cache_key)
        if cached is not None:
            return cached

        crawl_result = self.enrichment_service.crawl_public_website_for_cnpj(
            website_url,
            stop_after_page=lambda page: bool(extract_cnpj_candidates_from_text(page.page_text)),
        )
        extracted_candidates = self._extract_website_cnpj_candidates(crawl_result)
        attempt_metadata = {
            "checked_pages_count": crawl_result.pages_attempted,
            "candidate_count": len(extracted_candidates),
            "skipped_due_to_budget": crawl_result.stop_reason in {"page_budget_exhausted", "timeout_budget_exhausted"},
        }
        if extracted_candidates:
            cached = _WebsiteExtractionCacheEntry(
                candidates=extracted_candidates,
                reason_code=None,
                skipped_reason=None,
                attempt_metadata=attempt_metadata,
            )
        else:
            reason_code, skipped_reason = self._classify_website_crawl_failure(crawl_result)
            cached = _WebsiteExtractionCacheEntry(
                candidates=[],
                reason_code=reason_code,
                skipped_reason=skipped_reason,
                attempt_metadata=attempt_metadata,
            )

        self._website_candidate_cache[cache_key] = cached
        return cached

    def _finalize_missing_cnpj_result(
        self,
        lead,
        *,
        actor: str,
        source_provider: str | None,
        reason_code: str,
        skipped_reason: str,
        attempt_metadata: dict[str, Any] | None = None,
        matched_by: str | None = None,
        candidate_summary: dict[str, Any] | None = None,
    ) -> CNPJEnrichmentRunResult:
        self._mark_attempt(
            lead,
            actor=actor,
            match_status="not_found",
            match_confidence=None,
            source_provider=source_provider,
            skipped_reason=skipped_reason,
            error_message=None,
            reason_code=reason_code,
            attempt_metadata=attempt_metadata,
            matched_by=matched_by,
            candidate_summary=candidate_summary,
        )
        return CNPJEnrichmentRunResult(
            lead_id=lead.id,
            business_name=lead.business_name,
            success=True,
            cnpj=None,
            legal_name=lead.legal_name,
            match_status="not_found",
            reason_code=reason_code,
            skipped_reason=skipped_reason,
            last_enriched_at=lead.cnpj_last_enriched_at,
        )

    def _maybe_defer_company_search_for_batch(
        self,
        lead,
        *,
        actor: str,
        attempt_metadata: dict[str, Any] | None,
    ) -> CNPJEnrichmentRunResult | None:
        if not self._uses_cnpja_commercial_company_search():
            return None

        if self._company_search_rate_limited_in_batch and self.settings.cnpja_stop_batch_on_rate_limit:
            return self._build_company_search_pending_retry_result(
                lead,
                actor=actor,
                attempt_metadata=attempt_metadata,
            )

        safe_batch_size = max(1, self.settings.cnpja_batch_size)
        if self._company_search_attempts_in_batch >= safe_batch_size:
            return self._build_company_search_pending_retry_result(
                lead,
                actor=actor,
                attempt_metadata=attempt_metadata,
            )

        self._company_search_attempts_in_batch += 1
        return None

    def _build_company_search_pending_retry_result(
        self,
        lead,
        *,
        actor: str,
        attempt_metadata: dict[str, Any] | None,
    ) -> CNPJEnrichmentRunResult:
        merged_attempt_metadata = self._merge_attempt_metadata(
            attempt_metadata,
            {
                "provider": "cnpja_commercial",
                "pending_retry": True,
                "cooldown_seconds": self.settings.cnpja_rate_limit_cooldown_seconds,
                "batch_size": self.settings.cnpja_batch_size,
            },
        )
        self._mark_attempt(
            lead,
            actor=actor,
            match_status="unknown",
            match_confidence=None,
            source_provider="cnpja_commercial",
            skipped_reason=COMPANY_SEARCH_RATE_LIMIT_RETRY_REASON,
            error_message=None,
            reason_code=REASON_COMPANY_SEARCH_PENDING_RETRY,
            attempt_metadata=merged_attempt_metadata,
        )
        return CNPJEnrichmentRunResult(
            lead_id=lead.id,
            business_name=lead.business_name,
            success=True,
            cnpj=lead.cnpj,
            legal_name=lead.legal_name,
            match_status="unknown",
            reason_code=REASON_COMPANY_SEARCH_PENDING_RETRY,
            skipped_reason=COMPANY_SEARCH_RATE_LIMIT_RETRY_REASON,
            last_enriched_at=lead.cnpj_last_enriched_at,
        )

    @staticmethod
    def _merge_attempt_metadata(
        existing: dict[str, Any] | None,
        provider_attempt_metadata: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if existing is None and provider_attempt_metadata is None:
            return None
        merged = dict(existing or {})
        if provider_attempt_metadata:
            merged["company_search"] = provider_attempt_metadata
        return merged

    @staticmethod
    def _is_cnpja_zero_candidates(provider_attempt_metadata: dict[str, Any] | None) -> bool:
        if not provider_attempt_metadata:
            return False
        return bool(
            provider_attempt_metadata.get("provider") == "cnpja_commercial"
            and provider_attempt_metadata.get("cnpja_zero_candidates")
        )

    def _uses_cnpja_commercial_company_search(self) -> bool:
        return bool(
            self.settings.cnpj_company_search_enabled
            and self.settings.cnpj_company_search_provider == "cnpja_commercial"
        )

    def _company_search_source_provider(self) -> str:
        if (
            self.settings.cnpj_company_search_enabled
            and self.settings.cnpj_company_search_provider == "cnpja_commercial"
        ):
            return "cnpja_commercial"
        if (
            self.settings.cnpj_company_search_enabled
            and self.settings.cnpj_company_search_provider == "cnpj_ws_premium"
        ):
            return "cnpj_ws_premium"
        if (
            self.settings.cnpj_company_search_enabled
            and self.settings.cnpj_company_search_provider == "cnpjota"
        ):
            return "cnpjota"
        if self.settings.cnpja_enable_company_search and self.settings.cnpja_search_endpoint:
            return "cnpja_search"
        if (
            self.settings.cnpj_company_search_enabled
            and self.settings.cnpj_company_search_provider == "cnpja_commercial"
        ):
            return "cnpja_commercial"
        return "company_search"

    def _classify_website_crawl_failure(
        self,
        crawl_result,
    ) -> tuple[str, str]:
        if crawl_result.skipped_reason:
            return REASON_SKIPPED_NO_WEBSITE, NO_WEBSITE_AVAILABLE_REASON

        notes = [note.lower() for note in (page.note for page in crawl_result.page_results) if note]
        pages_fetched_ok = sum(
            1
            for page in crawl_result.page_results
            if page.http_status and page.http_status < 400 and page.page_text
        )
        has_timeout = crawl_result.stop_reason == "timeout_budget_exhausted" or any(
            "timed out" in note or "timeout" in note for note in notes
        )
        has_request_failure = any("request failed" in note for note in notes)

        if has_timeout and pages_fetched_ok == 0:
            return REASON_WEBSITE_TIMEOUT, WEBSITE_TIMEOUT_REASON
        if has_request_failure and pages_fetched_ok == 0:
            return REASON_WEBSITE_UNREACHABLE, WEBSITE_UNREACHABLE_REASON
        return REASON_NO_CNPJ_ON_WEBSITE, NO_WEBSITE_CNPJ_REASON

    def _extract_website_cnpj_candidates(
        self,
        crawl_result,
    ) -> list[_WebsiteCNPJCandidate]:
        candidates: dict[str, _WebsiteCNPJCandidate] = {}
        for page_result in crawl_result.page_results:
            if not page_result.page_text:
                continue
            for cnpj in extract_cnpj_candidates_from_text(page_result.page_text):
                current = candidates.get(cnpj)
                if current is None:
                    candidates[cnpj] = _WebsiteCNPJCandidate(
                        cnpj=cnpj,
                        source_urls=[page_result.source_url],
                        page_types=[page_result.page_type],
                    )
                    continue
                current.source_urls = unique_preserve_order([*current.source_urls, page_result.source_url])
                current.page_types = unique_preserve_order([*current.page_types, page_result.page_type])
        return list(candidates.values())

    def _score_website_candidate(
        self,
        lead,
        lookup: CNPJLookupResult,
        extracted_candidate: _WebsiteCNPJCandidate,
    ) -> _ScoredCandidate:
        evidence: dict[str, int] = {"website_extracted": 40}
        penalties: list[str] = []
        score = 40

        lead_name = normalize_business_name(lead.business_name)
        candidate_names = {
            value
            for value in (
                normalize_business_name(lookup.trade_name),
                normalize_business_name(lookup.legal_name),
            )
            if value
        }
        strong_name_match = False
        if lead_name and candidate_names:
            if lead_name in candidate_names:
                evidence["name"] = 20
                score += 20
                strong_name_match = True
            elif any(self._is_strong_name_variant(lead_name, candidate_name) for candidate_name in candidate_names):
                evidence["name"] = 12
                score += 12

        lead_city = normalize_text(lead.city)
        candidate_city = normalize_text(lookup.city)
        if lead_city and candidate_city:
            if lead_city == candidate_city:
                evidence["city"] = 15
                score += 15
            else:
                score -= 25
                penalties.append("different_city")

        lead_state = normalize_brazilian_state(lead.state) or normalize_text(lead.state)
        candidate_state = normalize_brazilian_state(lookup.state) or normalize_text(lookup.state)
        if lead_state and candidate_state:
            if lead_state == candidate_state:
                evidence["state"] = 10
                score += 10
            else:
                score -= 35
                penalties.append("different_state")

        lead_numbers = {
            value
            for value in (
                normalize_phone_br(lead.phone),
                normalize_phone_br(lead.whatsapp),
            )
            if value
        }
        candidate_numbers = {
            value for value in (normalize_phone_br(phone) for phone in lookup.phones) if value
        }
        if lead_numbers and candidate_numbers and lead_numbers.intersection(candidate_numbers):
            evidence["phone"] = 25
            score += 25

        lead_street, _ = split_street_and_number(
            lead.address,
            neighborhood=lead.neighborhood,
            city=lead.city,
            state=lead.state,
            postal_code=lead.postal_code,
        )
        candidate_street, _ = split_street_and_number(
            lookup.address,
            city=lookup.city,
            state=lookup.state,
            postal_code=lookup.postal_code,
        )
        normalized_lead_street = normalize_text(lead_street)
        normalized_candidate_street = normalize_text(candidate_street)
        normalized_lead_neighborhood = normalize_text(lead.neighborhood)
        normalized_candidate_neighborhood = normalize_text(
            (lookup.metadata or {}).get("neighborhood")
            if isinstance((lookup.metadata or {}).get("neighborhood"), str)
            else None
        )
        if (
            normalized_lead_street
            and normalized_candidate_street
            and normalized_lead_street == normalized_candidate_street
        ) or (
            normalized_lead_neighborhood
            and normalized_candidate_neighborhood
            and normalized_lead_neighborhood == normalized_candidate_neighborhood
        ):
            evidence["address"] = 15
            score += 15

        supportive_signal_count = sum(
            1 for key in ("name", "city", "state", "phone", "address") if key in evidence
        )
        return _ScoredCandidate(
            candidate=lookup,
            score=max(score, 0),
            evidence=evidence,
            penalties=penalties,
            strong_name_match=strong_name_match,
            supportive_signal_count=supportive_signal_count,
            source_urls=extracted_candidate.source_urls,
            page_types=extracted_candidate.page_types,
            matched_by="website_cnpj",
        )

    def _lookup_known_cnpj_cached(self, cnpj: str) -> CNPJLookupResult:
        cached = self._lookup_cache.get(cnpj)
        if cached is not None:
            if cached.result is not None:
                return cached.result
            if cached.not_found:
                raise CNPJANotFoundError()
            raise CNPJAProviderError(cached.error_message or "Provider lookup failed.", status_code=503)

        try:
            result = self.provider.lookup_known_cnpj(cnpj)
        except CNPJANotFoundError:
            self._lookup_cache[cnpj] = _LookupCacheEntry(not_found=True)
            raise
        except CNPJAProviderError as exc:
            self._lookup_cache[cnpj] = _LookupCacheEntry(error_message=str(exc))
            raise

        self._lookup_cache[cnpj] = _LookupCacheEntry(result=result)
        return result

    def _apply_lookup_result(
        self,
        lead,
        lookup: CNPJLookupResult,
        *,
        actor: str,
        match_confidence: float,
        matched_by: str,
        candidate_summary: dict[str, Any] | None,
        attempt_metadata: dict[str, Any] | None = None,
        reason_code: str = REASON_MATCHED,
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
            reason_code=reason_code,
            attempt_metadata=attempt_metadata,
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
            reason_code=reason_code,
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
        reason_code: str | None,
        attempt_metadata: dict[str, Any] | None = None,
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
            reason_code=reason_code,
            attempt_metadata=attempt_metadata,
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
                    "reason_code": reason_code,
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
        source_provider: str | None,
        reason_code: str,
        attempt_metadata: dict[str, Any] | None = None,
    ) -> CNPJEnrichmentRunResult:
        self.db.rollback()
        self._mark_attempt(
            lead,
            actor=actor,
            match_status="error",
            match_confidence=None,
            source_provider=source_provider or lead.cnpj_source_provider or self.settings.cnpj_lookup_provider,
            skipped_reason=None,
            error_message=error_message,
            reason_code=reason_code,
            attempt_metadata=attempt_metadata,
        )
        errors.append(f"Lead {lead.id}: {error_message}")
        return CNPJEnrichmentRunResult(
            lead_id=lead.id,
            business_name=lead.business_name,
            success=False,
            cnpj=lead.cnpj,
            legal_name=lead.legal_name,
            match_status="error",
            reason_code=reason_code,
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
            evidence["address"] = 15
            score += 15
        if lead_number and candidate_number and lead_number != candidate_number:
            score -= 10
            penalties.append("different_number")

        lead_postal = self._normalize_postal_code(lead.postal_code)
        candidate_postal = self._normalize_postal_code(candidate.postal_code)
        if lead_postal and candidate_postal and lead_postal == candidate_postal:
            evidence["postal_code"] = 25
            score += 25

        lead_city = normalize_text(lead.city)
        candidate_city = normalize_text(candidate.city)
        if lead_city and candidate_city:
            if lead_city == candidate_city:
                evidence["city"] = 15
                score += 15
            else:
                score -= 30
                penalties.append("different_city")

        lead_state = normalize_brazilian_state(lead.state) or normalize_text(lead.state)
        candidate_state = normalize_brazilian_state(candidate.state) or normalize_text(candidate.state)
        if lead_state and candidate_state:
            if lead_state == candidate_state:
                evidence["state"] = 10
                score += 10
            else:
                score -= 40
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
            source_urls=[],
            page_types=[],
            matched_by="company_search",
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

    def _get_website_batch_limit_error(self, pending_search_count: int) -> CNPJAProviderError | None:
        if pending_search_count <= MAX_WEBSITE_FALLBACK_BATCH:
            return None
        return CNPJAProviderError(WEBSITE_BATCH_LIMIT_MESSAGE, status_code=503)

    def _get_public_lookup_batch_limit_error(self, pending_lookup_count: int) -> CNPJAProviderError | None:
        if pending_lookup_count <= OPEN_API_BATCH_LIMIT:
            return None
        if self.settings.cnpj_lookup_provider == "cnpj_ws":
            return CNPJAProviderError(CNPJ_WS_PUBLIC_BATCH_LIMIT_MESSAGE, status_code=503)
        return CNPJAProviderError(CNPJA_OPEN_PUBLIC_BATCH_LIMIT_MESSAGE, status_code=503)

    @staticmethod
    def _provider_reason_code(error_message: str, *, company_search: bool = False) -> str:
        normalized_message = error_message.lower()
        if "usage limit" in normalized_message or "at most 3" in normalized_message:
            return (
                REASON_COMPANY_SEARCH_RATE_LIMITED
                if company_search
                else REASON_CNPJ_PROVIDER_RATE_LIMITED
            )
        return REASON_COMPANY_SEARCH_PROVIDER_ERROR if company_search else REASON_PROVIDER_ERROR

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
    def _candidate_has_confirmable_cnpj(candidate: _ScoredCandidate) -> bool:
        if not normalize_cnpj(candidate.candidate.cnpj):
            return False
        metadata = candidate.candidate.metadata or {}
        return bool(metadata.get("full_cnpj_available", True))

    def _candidate_requires_preview_review(self, candidate: _ScoredCandidate) -> bool:
        metadata = candidate.candidate.metadata or {}
        if not metadata.get("preview_mode"):
            return False
        if self._candidate_has_confirmable_cnpj(candidate):
            return False
        return candidate.score >= MEDIUM_CONFIDENCE_SCORE and not self._has_location_conflict(candidate)

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
            "source_urls": candidate.source_urls,
            "page_types": candidate.page_types,
            "matched_by": candidate.matched_by,
        }

    @staticmethod
    def _build_metadata(
        current_metadata: dict | None,
        *,
        lookup: CNPJLookupResult | None,
        match_status: str,
        skipped_reason: str | None,
        error_message: str | None,
        reason_code: str | None,
        attempt_metadata: dict[str, Any] | None = None,
        matched_by: str | None = None,
        candidate_summary: dict[str, Any] | None = None,
    ) -> dict:
        metadata = dict(current_metadata or {})
        metadata.update(
            {
                "match_status": match_status,
                "reason_code": reason_code,
                "skipped_reason": skipped_reason,
                "error_message": error_message,
            }
        )
        if matched_by:
            metadata["matched_by"] = matched_by
        if candidate_summary is not None:
            metadata["candidate_summary"] = candidate_summary
        if attempt_metadata is not None:
            metadata["crawl_summary"] = attempt_metadata
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
            no_website_count=sum(1 for item in results if item.reason_code == REASON_SKIPPED_NO_WEBSITE),
            no_cnpj_on_website_count=sum(1 for item in results if item.reason_code == REASON_NO_CNPJ_ON_WEBSITE),
            website_timeout_count=sum(1 for item in results if item.reason_code == REASON_WEBSITE_TIMEOUT),
            website_unreachable_count=sum(
                1 for item in results if item.reason_code == REASON_WEBSITE_UNREACHABLE
            ),
            validation_failed_count=sum(
                1 for item in results if item.reason_code == REASON_CNPJ_VALIDATION_FAILED
            ),
            low_confidence_count=sum(1 for item in results if item.reason_code == REASON_LOW_CONFIDENCE),
            company_search_matched_count=sum(
                1 for item in results if item.reason_code == REASON_COMPANY_SEARCH_MATCHED
            ),
            company_search_needs_review_count=sum(
                1
                for item in results
                if item.reason_code in {REASON_COMPANY_SEARCH_NEEDS_REVIEW, REASON_COMPANY_SEARCH_PREVIEW_ONLY}
            ),
            company_search_no_candidates_count=sum(
                1
                for item in results
                if item.reason_code in {REASON_COMPANY_SEARCH_NO_CANDIDATES, REASON_CNPJA_ZERO_CANDIDATES}
            ),
            company_search_zero_candidates_count=sum(
                1 for item in results if item.reason_code == REASON_CNPJA_ZERO_CANDIDATES
            ),
            company_search_low_confidence_count=sum(
                1 for item in results if item.reason_code == REASON_COMPANY_SEARCH_LOW_CONFIDENCE
            ),
            company_search_not_configured_count=sum(
                1 for item in results if item.reason_code == REASON_COMPANY_SEARCH_NOT_CONFIGURED
            ),
            company_search_pending_retry_count=sum(
                1 for item in results if item.reason_code == REASON_COMPANY_SEARCH_PENDING_RETRY
            ),
            company_search_rate_limited_count=sum(
                1 for item in results if item.reason_code == REASON_COMPANY_SEARCH_RATE_LIMITED
            ),
            company_search_provider_error_count=sum(
                1 for item in results if item.reason_code == REASON_COMPANY_SEARCH_PROVIDER_ERROR
            ),
            provider_rate_limited_count=sum(
                1 for item in results if item.reason_code == REASON_CNPJ_PROVIDER_RATE_LIMITED
            ),
            provider_error_count=sum(1 for item in results if item.reason_code == REASON_PROVIDER_ERROR),
            error_count=sum(1 for item in results if not item.success or item.match_status == "error"),
            errors=errors,
        )
