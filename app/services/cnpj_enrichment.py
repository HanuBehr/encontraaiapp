from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
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
    LeadBatchApproveCNPJCandidatesResponse,
    LeadBatchApproveCNPJCandidatesSummary,
    LeadBatchCNPJEnrichmentResponse,
    LeadBatchCNPJEnrichmentSummary,
)
from app.services.cnpj_category_cnae import category_activity_matches, find_category_cnae_hint
from app.services.enrichment import EnrichmentService
from app.services.geo.ibge_municipalities import (
    lookup_expected_phone_area,
    lookup_ibge_municipality_code,
)
from app.services.normalization import (
    clean_email,
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
    build_company_search_name_variant_groups,
    normalize_cnpj,
    resolve_company_searchable_domain,
    resolve_validated_phone_area,
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
REVIEWABLE_COMPANY_SEARCH_SCORE = 50
CLEAR_WINNER_GAP = 10
MAX_WEBSITE_CNPJ_CANDIDATES = 3
MAX_WEBSITE_FALLBACK_BATCH = 10
_CNPJ_PATTERN = re.compile(r"(?<!\d)(?:\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}|\d{14})(?!\d)")
_ZIP_PATTERN = re.compile(r"(?<!\d)(\d{5})-?(\d{3})(?!\d)")

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
REASON_PAID_SEARCH_RECENTLY_ATTEMPTED = "paid_search_recently_attempted"
REASON_SKIPPED_REVIEW_CANDIDATE_EXISTS = "skipped_review_candidate_exists"
BLOCKED_REASON_MISSING_FULL_CNPJ = "missing_full_cnpj"
BLOCKED_REASON_CITY_STATE_CONFLICT = "city_state_conflict"
BLOCKED_REASON_AMBIGUOUS_TOP_CANDIDATES = "ambiguous_top_candidates"
BLOCKED_REASON_PROVIDER_PREVIEW_MASKED = "provider_preview_masked"
BLOCKED_REASON_INSUFFICIENT_IDENTITY_SUPPORT = "insufficient_identity_support"
BLOCKED_REASON_BELOW_AUTOFILL_THRESHOLD = "below_autofill_threshold"

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
APPROVE_CNPJ_CANDIDATE_ERROR_MESSAGE = "Nenhum CNPJ revisável disponível para este lead."
PAID_SEARCH_RECENTLY_ATTEMPTED_REASON = (
    "Busca paga já realizada recentemente para este lead. Use força/limpeza manual se quiser tentar novamente."
)
REVIEW_CANDIDATE_EXISTS_REASON = "Candidato encontrado. Revise e aprove antes de consultar novamente."
REVIEW_CANDIDATE_REJECTED_REASON = "Candidato revisado e mantido sem CNPJ."
PAID_SEARCH_REPEATABLE_REASON_CODES = {
    REASON_COMPANY_SEARCH_NO_CANDIDATES,
    REASON_CNPJA_ZERO_CANDIDATES,
    REASON_COMPANY_SEARCH_LOW_CONFIDENCE,
    REASON_COMPANY_SEARCH_NEEDS_REVIEW,
    REASON_COMPANY_SEARCH_PREVIEW_ONLY,
}
COMPANY_SEARCH_EXECUTED_REASON_CODES = {
    REASON_COMPANY_SEARCH_MATCHED,
    REASON_COMPANY_SEARCH_NEEDS_REVIEW,
    REASON_COMPANY_SEARCH_PREVIEW_ONLY,
    REASON_COMPANY_SEARCH_NO_CANDIDATES,
    REASON_CNPJA_ZERO_CANDIDATES,
    REASON_COMPANY_SEARCH_LOW_CONFIDENCE,
    REASON_COMPANY_SEARCH_PROVIDER_ERROR,
    REASON_COMPANY_SEARCH_RATE_LIMITED,
}


@dataclass(slots=True)
class _PendingLookup:
    lead_id: int
    cnpj: str


@dataclass(slots=True)
class _PendingSearch:
    lead_id: int


@dataclass(slots=True)
class _EvidenceProfile:
    lead_id: int
    business_name: str
    category: str | None
    city: str | None
    state: str | None
    municipality_ibge_code: str | None
    address_raw: str | None
    street_name: str | None
    address_number: str | None
    neighborhood: str | None
    postal_code: str | None
    extracted_zip_from_address: bool
    phone: str | None
    whatsapp: str | None
    phone_digits: list[str]
    raw_phone_area: str | None
    phone_area: str | None
    expected_phone_area: str | None
    phone_area_conflict: bool
    website_url: str | None
    website_domain: str | None
    email: str | None
    email_domain: str | None
    searchable_email_domain: str | None
    searchable_email_domain_source: str | None
    instagram: str | None
    google_maps_url: str | None
    existing_contacts: list[dict[str, str]]
    alias_variants: list[str]
    names_variants: list[str]
    legal_name_variants: list[str]
    brand_variants: list[str]
    category_cnae_group: list[str]

    def to_summary(self) -> dict[str, Any]:
        return {
            "lead_id": self.lead_id,
            "business_name": self.business_name,
            "category": self.category,
            "city": self.city,
            "state": self.state,
            "municipality_ibge_code": self.municipality_ibge_code,
            "address_raw": self.address_raw,
            "street_name": self.street_name,
            "address_number": self.address_number,
            "neighborhood": self.neighborhood,
            "postal_code": self.postal_code,
            "extracted_zip_from_address": self.extracted_zip_from_address,
            "phone": self.phone,
            "whatsapp": self.whatsapp,
            "raw_phone_area": self.raw_phone_area,
            "phone_area": self.phone_area,
            "expected_phone_area": self.expected_phone_area,
            "phone_area_conflict": self.phone_area_conflict,
            "website_url": self.website_url,
            "website_domain": self.website_domain,
            "email": self.email,
            "email_domain": self.email_domain,
            "searchable_email_domain": self.searchable_email_domain,
            "searchable_email_domain_source": self.searchable_email_domain_source,
            "instagram": self.instagram,
            "google_maps_url": self.google_maps_url,
            "existing_contacts": self.existing_contacts,
            "alias_variants": self.alias_variants,
            "names_variants": self.names_variants,
            "legal_name_variants": self.legal_name_variants,
            "brand_variants": self.brand_variants,
            "category_cnae_group": self.category_cnae_group,
        }


@dataclass(slots=True)
class _CommercialAttemptPlan:
    mode: str
    label: str
    reason: str
    params: dict[str, str]
    searched_values: list[str]
    query_param: str | None = None
    run_condition: str = "always"
    domain_source: str | None = None


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
    alias_match: bool
    legal_name_match: bool
    person_like_legal_name: bool
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


class CNPJCandidateApprovalError(ValueError):
    pass


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
        self._paid_search_signature_cache: set[str] = set()
        self._paid_calls_made = 0
        self._paid_calls_skipped_duplicate = 0
        self._paid_calls_skipped_recent = 0
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
        search_mode: str | None = None,
        force_paid_search: bool = False,
        actor: str = "system",
        scope_label: str = "lead ids",
    ) -> LeadBatchCNPJEnrichmentResponse:
        requested_ids = [int(lead_id) for lead_id in dict.fromkeys(lead_ids)]
        self._lookup_cache = {}
        self._website_candidate_cache = {}
        self._company_search_attempts_in_batch = 0
        self._company_search_rate_limited_in_batch = False
        self._paid_search_signature_cache = set()
        self._paid_calls_made = 0
        self._paid_calls_skipped_duplicate = 0
        self._paid_calls_skipped_recent = 0
        effective_search_mode = self._resolve_search_mode(search_mode)
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

            if lead.cnpj and lead.cnpj_match_status == "matched":
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

            if not force:
                reviewable_candidate = self._get_reviewable_candidate_summary(lead)
                if reviewable_candidate is not None:
                    results.append(
                        self._build_review_candidate_skip_result(
                            lead,
                            actor=actor,
                            candidate_summary=reviewable_candidate,
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

            if (
                not force_paid_search
                and self.settings.cnpj_company_search_configured
                and not self._uses_cnpja_commercial_company_search()
            ):
                recent_search_skip = self._build_recent_paid_search_skip_result(
                    lead,
                    actor=actor,
                    search_mode=effective_search_mode,
                )
                if recent_search_skip is not None:
                    results.append(recent_search_skip)
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
            results.append(
                self._enrich_missing_cnpj_lead(
                    lead,
                    actor=actor,
                    errors=errors,
                    search_mode=effective_search_mode,
                    force_paid_search=force_paid_search,
                )
            )

        for lookup in pending_lookups:
            lead = lead_map[lookup.lead_id]
            results.append(self._enrich_known_cnpj_lead(lead, lookup.cnpj, actor=actor, errors=errors))

        summary = self._build_summary(
            requested_ids=requested_ids,
            results=results,
            errors=errors,
            scope_label=scope_label,
            paid_calls_made=self._paid_calls_made,
            paid_calls_skipped_duplicate=self._paid_calls_skipped_duplicate,
            paid_calls_skipped_recent=self._paid_calls_skipped_recent,
        )
        return LeadBatchCNPJEnrichmentResponse(
            processed=len(results),
            results=results,
            summary=summary,
        )

    def approve_cnpj_candidate(
        self,
        lead_id: int,
        *,
        candidate_cnpj: str | None = None,
        actor: str = "system",
    ):
        lead = self.repository.get_by_id(lead_id)
        if lead is None:
            raise ValueError(f"Lead {lead_id} not found.")

        candidate_summary = self._resolve_candidate_summary_for_approval(
            lead,
            candidate_cnpj=candidate_cnpj,
        )
        if candidate_summary is None:
            raise CNPJCandidateApprovalError(APPROVE_CNPJ_CANDIDATE_ERROR_MESSAGE)

        candidate_cnpj = normalize_cnpj(candidate_summary.get("cnpj"))
        if candidate_cnpj is None:
            raise CNPJCandidateApprovalError(APPROVE_CNPJ_CANDIDATE_ERROR_MESSAGE)
        if candidate_summary.get("manual_review_approvable") is False:
            raise CNPJCandidateApprovalError(APPROVE_CNPJ_CANDIDATE_ERROR_MESSAGE)

        previous_status = lead.cnpj_match_status
        approved_at = utcnow()
        lead.cnpj = candidate_cnpj

        legal_name = self._candidate_summary_text(candidate_summary, "legal_name")
        if legal_name:
            lead.legal_name = legal_name

        lead.cnpj_match_status = "matched"
        lead.cnpj_match_confidence = self._candidate_summary_confidence(candidate_summary, lead.cnpj_match_confidence)
        lead.cnpj_last_enriched_at = approved_at

        provider = self._candidate_summary_text(candidate_summary, "provider")
        if provider:
            lead.cnpj_source_provider = provider

        metadata = dict(lead.cnpj_metadata_json or {})
        metadata.update(
            {
                "match_status": "matched",
                "reason_code": REASON_MATCHED,
                "skipped_reason": None,
                "error_message": None,
                "candidate_summary": candidate_summary,
                "candidate_summaries": self._get_candidate_summaries_if_present(lead),
                "approved_manually": True,
                "approved_at": approved_at.isoformat(),
                "previous_status": previous_status,
            }
        )
        lead.cnpj_metadata_json = metadata

        self.db.add(
            ActivityLog(
                organization_id=lead.organization_id or self.repository.organization_id,
                lead_id=lead.id,
                entity_type="lead",
                entity_id=lead.id,
                action=ActivityAction.ENRICHED,
                actor=actor,
                message="CNPJ candidate approved manually.",
                metadata_json={
                    "enrichment_type": "cnpj",
                    "approval_action": "approved",
                    "cnpj": lead.cnpj,
                    "legal_name": lead.legal_name,
                    "previous_status": previous_status,
                    "source_provider": lead.cnpj_source_provider,
                },
            )
        )
        self.db.commit()
        approved_lead = self.repository.get_detail(lead_id)
        if approved_lead is None:
            raise ValueError(f"Lead {lead_id} not found.")
        return approved_lead

    def reject_cnpj_candidate(
        self,
        lead_id: int,
        *,
        candidate_cnpj: str | None = None,
        actor: str = "system",
    ):
        lead = self.repository.get_by_id(lead_id)
        if lead is None:
            raise ValueError(f"Lead {lead_id} not found.")

        candidate_summary = self._resolve_candidate_summary_for_approval(
            lead,
            candidate_cnpj=candidate_cnpj,
        )
        if candidate_summary is None:
            raise CNPJCandidateApprovalError(APPROVE_CNPJ_CANDIDATE_ERROR_MESSAGE)

        previous_status = lead.cnpj_match_status
        rejected_at = utcnow()
        lead.cnpj_match_status = "not_found"
        lead.cnpj_match_confidence = None
        lead.cnpj_last_enriched_at = rejected_at
        metadata = dict(lead.cnpj_metadata_json or {})
        metadata.update(
            {
                "match_status": "not_found",
                "reason_code": REASON_LOW_CONFIDENCE,
                "skipped_reason": REVIEW_CANDIDATE_REJECTED_REASON,
                "error_message": None,
                "candidate_summary": candidate_summary,
                "candidate_summaries": self._get_candidate_summaries_if_present(lead),
                "rejected_manually": True,
                "rejected_at": rejected_at.isoformat(),
                "previous_status": previous_status,
            }
        )
        lead.cnpj_metadata_json = metadata

        self.db.add(
            ActivityLog(
                organization_id=lead.organization_id or self.repository.organization_id,
                lead_id=lead.id,
                entity_type="lead",
                entity_id=lead.id,
                action=ActivityAction.ENRICHED,
                actor=actor,
                message="CNPJ candidate rejected manually.",
                metadata_json={
                    "enrichment_type": "cnpj",
                    "approval_action": "rejected",
                    "candidate_cnpj": candidate_summary.get("cnpj"),
                    "previous_status": previous_status,
                    "source_provider": candidate_summary.get("provider"),
                },
            )
        )
        self.db.commit()
        rejected_lead = self.repository.get_detail(lead_id)
        if rejected_lead is None:
            raise ValueError(f"Lead {lead_id} not found.")
        return rejected_lead

    def approve_cnpj_candidates_batch(
        self,
        lead_ids: list[int],
        *,
        actor: str = "system",
    ) -> LeadBatchApproveCNPJCandidatesResponse:
        requested_ids = [int(lead_id) for lead_id in dict.fromkeys(lead_ids)]
        summary = LeadBatchApproveCNPJCandidatesSummary(requested=len(requested_ids))

        for lead_id in requested_ids:
            lead = self.repository.get_by_id(lead_id)
            if lead is None:
                summary.errors.append(f"Lead {lead_id} not found.")
                continue
            summary.processed += 1

            if lead.cnpj_match_status == "matched" and lead.cnpj:
                summary.skipped_already_matched_count += 1
                continue

            candidate_summaries = self._get_candidate_summaries_if_present(lead)
            reviewable_candidates = [
                item
                for item in candidate_summaries
                if normalize_cnpj(item.get("cnpj")) is not None and item.get("manual_review_approvable") is not False
            ]

            if not reviewable_candidates:
                summary.skipped_no_candidate_count += 1
                continue

            if len(reviewable_candidates) > 1:
                summary.skipped_ambiguous_count += 1
                continue

            candidate_summary = reviewable_candidates[0]
            confidence = self._candidate_summary_confidence(candidate_summary, None)
            if confidence is None or confidence < self._score_to_confidence(REVIEWABLE_COMPANY_SEARCH_SCORE):
                summary.skipped_low_confidence_count += 1
                continue

            self.approve_cnpj_candidate(
                lead.id,
                candidate_cnpj=candidate_summary.get("cnpj"),
                actor=actor,
            )
            summary.approved_count += 1

        return LeadBatchApproveCNPJCandidatesResponse(summary=summary)

    def _build_review_candidate_skip_result(
        self,
        lead,
        *,
        actor: str,
        candidate_summary: dict[str, Any],
    ) -> CNPJEnrichmentRunResult:
        candidate_summaries = self._get_candidate_summaries_if_present(lead)
        self._mark_attempt(
            lead,
            actor=actor,
            match_status="needs_review",
            match_confidence=self._candidate_summary_confidence(candidate_summary, lead.cnpj_match_confidence),
            source_provider=self._candidate_summary_text(candidate_summary, "provider") or lead.cnpj_source_provider,
            skipped_reason=REVIEW_CANDIDATE_EXISTS_REASON,
            error_message=None,
            reason_code=REASON_SKIPPED_REVIEW_CANDIDATE_EXISTS,
            candidate_summary=candidate_summary,
            candidate_summaries=candidate_summaries,
        )
        return CNPJEnrichmentRunResult(
            lead_id=lead.id,
            business_name=lead.business_name,
            success=True,
            cnpj=lead.cnpj,
            legal_name=lead.legal_name,
            match_status="needs_review",
            match_confidence=lead.cnpj_match_confidence,
            reason_code=REASON_SKIPPED_REVIEW_CANDIDATE_EXISTS,
            skipped_reason=REVIEW_CANDIDATE_EXISTS_REASON,
            last_enriched_at=lead.cnpj_last_enriched_at,
        )

    def _build_recent_paid_search_skip_result(
        self,
        lead,
        *,
        actor: str,
        search_mode: str | None = None,
    ) -> CNPJEnrichmentRunResult | None:
        provider = self._company_search_source_provider()
        signature_payload = self._build_company_search_signature_payload(
            lead,
            provider=provider,
            search_mode=search_mode,
        )
        signature = self._build_company_search_signature(signature_payload)
        if not self._should_skip_recent_paid_search(lead, signature=signature, provider=provider):
            return None

        attempt_metadata = self._build_recent_paid_search_attempt_metadata(
            lead,
            signature=signature,
            signature_payload=signature_payload,
            provider=provider,
        )
        match_status = getattr(lead, "cnpj_match_status", None) or "unknown"
        candidate_summary = self._get_candidate_summary_if_present(lead)
        candidate_summaries = self._get_candidate_summaries_if_present(lead)
        self._mark_attempt(
            lead,
            actor=actor,
            match_status=match_status,
            match_confidence=lead.cnpj_match_confidence,
            source_provider=lead.cnpj_source_provider or provider,
            skipped_reason=PAID_SEARCH_RECENTLY_ATTEMPTED_REASON,
            error_message=None,
            reason_code=REASON_PAID_SEARCH_RECENTLY_ATTEMPTED,
            attempt_metadata=attempt_metadata,
            candidate_summary=candidate_summary,
            candidate_summaries=candidate_summaries,
        )
        return CNPJEnrichmentRunResult(
            lead_id=lead.id,
            business_name=lead.business_name,
            success=True,
            cnpj=lead.cnpj,
            legal_name=lead.legal_name,
            match_status=match_status,
            match_confidence=lead.cnpj_match_confidence,
            reason_code=REASON_PAID_SEARCH_RECENTLY_ATTEMPTED,
            skipped_reason=PAID_SEARCH_RECENTLY_ATTEMPTED_REASON,
            last_enriched_at=lead.cnpj_last_enriched_at,
        )

    @staticmethod
    def _should_skip_paid_planning(
        lead,
        *,
        force_paid_search: bool = False,
    ) -> tuple[bool, str | None]:
        if not force_paid_search and getattr(lead, "cnpj", None) and getattr(lead, "cnpj_match_status", None) == "matched":
            return True, "Skipped: lead already has confirmed CNPJ."
        return False, None

    def _should_skip_recent_paid_search(
        self,
        lead,
        *,
        signature: str,
        provider: str,
    ) -> bool:
        metadata = lead.cnpj_metadata_json or {}
        last_signature = metadata.get("cnpj_paid_search_last_signature")
        last_provider = metadata.get("cnpj_paid_search_last_provider")
        last_reason_code = metadata.get("cnpj_paid_search_last_result_status")
        last_attempt_at = self._parse_metadata_datetime(metadata.get("cnpj_paid_search_last_attempt_at"))
        if (
            not isinstance(last_signature, str)
            or last_signature != signature
            or not isinstance(last_provider, str)
            or last_provider != provider
            or not isinstance(last_reason_code, str)
            or last_reason_code not in PAID_SEARCH_REPEATABLE_REASON_CODES
            or last_attempt_at is None
        ):
            return False
        cooldown = timedelta(hours=max(1, self.settings.cnpj_paid_search_repeat_cooldown_hours))
        return utcnow() - last_attempt_at < cooldown

    def _build_recent_paid_search_attempt_metadata(
        self,
        lead,
        *,
        signature: str,
        signature_payload: dict[str, Any],
        provider: str,
    ) -> dict[str, Any]:
        metadata = dict(lead.cnpj_metadata_json or {})
        last_attempt_at = metadata.get("cnpj_paid_search_last_attempt_at")
        last_result_status = metadata.get("cnpj_paid_search_last_result_status")
        last_candidates_count = metadata.get("cnpj_paid_search_last_candidates_count")
        return {
            "company_search": {
                "provider": provider,
                "actual_request_made": False,
                "recent_search_skipped": True,
                "query_signature": signature,
                "signature_payload": signature_payload,
                "repeat_cooldown_hours": self.settings.cnpj_paid_search_repeat_cooldown_hours,
                "last_attempt_at": last_attempt_at,
                "last_result_status": last_result_status,
                "last_candidates_count": last_candidates_count,
            }
        }

    def _build_company_search_signature_payload(
        self,
        lead,
        *,
        provider: str,
        search_mode: str | None = None,
    ) -> dict[str, Any]:
        normalized_business_name = normalize_text(lead.business_name)
        normalized_state = normalize_brazilian_state(lead.state) or normalize_text(lead.state)
        normalized_postal_code = self._normalize_postal_code(lead.postal_code)
        extracted_postal_code = (
            normalized_postal_code
            or self._extract_postal_code_from_text(getattr(lead, "address", None))
        )
        municipality_code = lookup_ibge_municipality_code(lead.city, lead.state)
        raw_phone_area = self._extract_area_code(lead.phone) or self._extract_area_code(lead.whatsapp)
        phone_area, _, _ = resolve_validated_phone_area(
            phone_area=raw_phone_area,
            city=lead.city,
            state=lead.state,
            municipality_code=municipality_code,
            allow_without_mapping=self.settings.cnpja_allow_unmapped_phone_area_filter,
        )
        searchable_email_domain, searchable_email_domain_source = resolve_company_searchable_domain(
            email_domain=self._extract_email_domain(getattr(lead, "email", None)),
            website_domain=normalize_domain(lead.website) or normalize_domain(lead.domain),
        )
        return {
            "lead_id": lead.id,
            "provider": provider,
            "business_name": normalized_business_name,
            "city": normalize_text(lead.city),
            "state": normalized_state,
            "municipality_code": municipality_code,
            "postal_code": extracted_postal_code,
            "phone_area": phone_area,
            "website_domain": normalize_domain(lead.website) or normalize_domain(lead.domain),
            "email_domain": self._extract_email_domain(getattr(lead, "email", None)),
            "searchable_email_domain": searchable_email_domain,
            "searchable_email_domain_source": searchable_email_domain_source,
            "query_mode": "staged_company_search",
            "search_mode": self._resolve_search_mode(search_mode),
            "max_attempts_per_lead": self.settings.cnpja_max_search_attempts_per_lead,
            "max_paid_calls_per_lead": self.settings.cnpja_max_paid_calls_per_lead,
            "name_variant_limit": self.settings.cnpja_name_variant_limit,
            "strict_address_attempt_enabled": self.settings.cnpja_enable_strict_address_attempt,
            "legal_name_attempt_enabled": self.settings.cnpja_enable_legal_name_attempt,
            "zip_fallback_enabled": self.settings.cnpja_enable_zip_fallback,
            "email_domain_search_enabled": self.settings.cnpja_enable_email_domain_search,
            "email_domain_filter_enabled": self.settings.cnpja_use_email_domain_filter,
        }

    @staticmethod
    def _build_company_search_signature(payload: dict[str, Any]) -> str:
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    @staticmethod
    def _parse_metadata_datetime(value: Any) -> datetime | None:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _resolve_search_mode(self, requested_mode: str | None) -> str:
        normalized = (requested_mode or self.settings.cnpja_search_mode or "balanced").strip().lower()
        if normalized not in {"cheap", "balanced", "delivery"}:
            return "balanced"
        return normalized

    @staticmethod
    def _extract_email_domain(value: str | None) -> str | None:
        email = clean_email(value)
        if not email or "@" not in email:
            return None
        domain = email.split("@", 1)[1].strip().lower()
        return domain or None

    def _build_evidence_profile(self, lead) -> _EvidenceProfile:
        normalized_postal_code = self._normalize_postal_code(getattr(lead, "postal_code", None))
        extracted_postal_code = normalized_postal_code or self._extract_postal_code_from_text(getattr(lead, "address", None))
        street_name, address_number = split_street_and_number(
            getattr(lead, "address", None),
            neighborhood=getattr(lead, "neighborhood", None),
            city=getattr(lead, "city", None),
            state=getattr(lead, "state", None),
            postal_code=extracted_postal_code,
        )
        if not address_number:
            address_number = self._extract_address_number_from_text(getattr(lead, "address", None))
        phone_values = [
            value
            for value in unique_preserve_order(
                [
                    normalize_phone_br(getattr(lead, "phone", None)),
                    normalize_phone_br(getattr(lead, "whatsapp", None)),
                ]
            )
            if value
        ]
        contacts_summary: list[dict[str, str]] = []
        for contact in getattr(lead, "contacts", []) or []:
            contact_type = getattr(contact, "contact_type", None)
            raw_value = getattr(contact, "raw_value", None)
            if not contact_type or not isinstance(raw_value, str) or not raw_value.strip():
                continue
            contacts_summary.append({"type": str(contact_type), "value": raw_value.strip()})

        email_domain = (
            self._extract_email_domain(getattr(lead, "email", None))
            or next(
                (
                    self._extract_email_domain(item["value"])
                    for item in contacts_summary
                    if item.get("type") == "email"
                ),
                None,
            )
        )
        website_domain = normalize_domain(getattr(lead, "website", None)) or normalize_domain(getattr(lead, "domain", None))
        searchable_email_domain, searchable_email_domain_source = resolve_company_searchable_domain(
            email_domain=email_domain,
            website_domain=website_domain,
        )
        variant_groups = build_company_search_name_variant_groups(
            getattr(lead, "business_name", ""),
            category=getattr(lead, "category", None),
            max_variants=self.settings.cnpja_name_variant_limit,
        )
        category_hint = find_category_cnae_hint(getattr(lead, "category", None))
        brand_variants = [
            variant
            for variant in variant_groups.alias_variants
            if len((normalize_text(variant) or "").split()) <= 3
        ]
        municipality_code = lookup_ibge_municipality_code(getattr(lead, "city", None), getattr(lead, "state", None))
        raw_phone_area = self._extract_area_code(getattr(lead, "phone", None)) or self._extract_area_code(
            getattr(lead, "whatsapp", None)
        )
        phone_area, phone_area_conflict, expected_phone_area = resolve_validated_phone_area(
            phone_area=raw_phone_area,
            city=getattr(lead, "city", None),
            state=getattr(lead, "state", None),
            municipality_code=municipality_code,
            allow_without_mapping=self.settings.cnpja_allow_unmapped_phone_area_filter,
        )
        return _EvidenceProfile(
            lead_id=lead.id,
            business_name=lead.business_name,
            category=getattr(lead, "category", None),
            city=getattr(lead, "city", None),
            state=normalize_brazilian_state(getattr(lead, "state", None)) or getattr(lead, "state", None),
            municipality_ibge_code=municipality_code,
            address_raw=getattr(lead, "address", None),
            street_name=street_name,
            address_number=address_number,
            neighborhood=getattr(lead, "neighborhood", None),
            postal_code=extracted_postal_code,
            extracted_zip_from_address=bool(extracted_postal_code and not normalized_postal_code),
            phone=getattr(lead, "phone", None),
            whatsapp=getattr(lead, "whatsapp", None),
            phone_digits=phone_values,
            raw_phone_area=raw_phone_area,
            phone_area=phone_area,
            expected_phone_area=expected_phone_area,
            phone_area_conflict=phone_area_conflict,
            website_url=getattr(lead, "website", None) or getattr(lead, "domain", None),
            website_domain=website_domain,
            email=getattr(lead, "email", None),
            email_domain=email_domain,
            searchable_email_domain=searchable_email_domain if self.settings.cnpja_enable_email_domain_search else None,
            searchable_email_domain_source=(
                searchable_email_domain_source if self.settings.cnpja_enable_email_domain_search else None
            ),
            instagram=getattr(lead, "instagram", None),
            google_maps_url=getattr(lead, "google_maps_url", None),
            existing_contacts=contacts_summary,
            alias_variants=variant_groups.alias_variants,
            names_variants=variant_groups.names_variants,
            legal_name_variants=variant_groups.legal_name_variants,
            brand_variants=brand_variants or variant_groups.alias_variants[:2],
            category_cnae_group=list(category_hint.activity_ids) if category_hint else [],
        )

    @staticmethod
    def _get_candidate_summary_if_present(lead) -> dict[str, Any] | None:
        candidate_summaries = CNPJEnrichmentService._get_candidate_summaries_if_present(lead)
        if not candidate_summaries:
            return None
        return dict(candidate_summaries[0])

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
        search_mode: str,
        force_paid_search: bool,
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
                search_mode=search_mode,
                force_paid_search=force_paid_search,
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
        search_mode: str,
        force_paid_search: bool,
    ) -> CNPJEnrichmentRunResult:
        evidence_profile = self._build_evidence_profile(lead)
        if self._uses_cnpja_commercial_company_search():
            return self._enrich_missing_cnpj_via_cnpja_commercial(
                lead,
                evidence_profile=evidence_profile,
                actor=actor,
                errors=errors,
                attempt_metadata=attempt_metadata,
                search_mode=search_mode,
                force_paid_search=force_paid_search,
            )

        provider_attempt_metadata: dict[str, Any] | None = None
        provider = self._company_search_source_provider()
        search_signature_payload = self._build_company_search_signature_payload(
            lead,
            provider=provider,
            search_mode=search_mode,
        )
        search_signature = self._build_company_search_signature(search_signature_payload)
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
            provider_attempt_metadata = self._with_company_search_request_metadata(
                getattr(self.provider, "last_company_search_metadata", None),
                query_signature=search_signature,
                signature_payload=search_signature_payload,
                provider=provider,
                actual_request_made=True,
            )
        except CNPJAProviderError as exc:
            provider_attempt_metadata = self._with_company_search_request_metadata(
                getattr(self.provider, "last_company_search_metadata", None),
                query_signature=search_signature,
                signature_payload=search_signature_payload,
                provider=provider,
                actual_request_made=True,
            )
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
                source_provider=provider,
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
                source_provider=provider,
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
            (self._score_candidate(evidence_profile, candidate) for candidate in candidates),
            key=lambda item: item.score,
            reverse=True,
        )
        best_candidate = scored_candidates[0]
        top_gap = (
            best_candidate.score - scored_candidates[1].score
            if len(scored_candidates) > 1
            else CLEAR_WINNER_GAP
        )
        strong_review_candidates = self._build_candidate_summaries(
            scored_candidates,
            best_score=best_candidate.score,
            prefer_strong_only=True,
        )
        ambiguous_strong_candidates = len(strong_review_candidates) > 1
        effective_top_gap = (
            top_gap
            if search_mode != "delivery" or ambiguous_strong_candidates
            else CLEAR_WINNER_GAP
        )
        blocked_reason = self._blocked_from_autofill_reason(
            best_candidate,
            top_gap=effective_top_gap,
            require_confirmable_cnpj=True,
        )
        candidate_summary = self._build_candidate_summary(
            best_candidate,
            candidate_count=len(scored_candidates),
            blocked_from_autofill_reason=blocked_reason,
            match_confidence=(
                self._review_confidence(best_candidate.score, blocked_reason)
                if blocked_reason
                else self._score_to_confidence(best_candidate.score)
            ),
        )
        candidate_summaries = (
            strong_review_candidates
            if ambiguous_strong_candidates
            else self._build_candidate_summaries(
                scored_candidates,
                best_score=best_candidate.score,
                prefer_strong_only=False,
            )
        )
        merged_attempt_metadata = self._attach_company_search_candidate_diagnostics(
            merged_attempt_metadata,
            best_candidate=best_candidate,
            candidate_summary=candidate_summary,
            candidates_returned_count=len(scored_candidates),
            rejection_reason=self._top_candidate_rejection_reason(
                best_candidate,
                blocked_reason=blocked_reason,
            ),
        )

        if self._is_high_confidence_match(best_candidate, top_gap=effective_top_gap) and blocked_reason is None:
            return self._apply_lookup_result(
                lead,
                best_candidate.candidate,
                actor=actor,
                match_confidence=self._score_to_confidence(best_candidate.score),
                matched_by="company_search",
                candidate_summary=candidate_summary,
                candidate_summaries=candidate_summaries,
                attempt_metadata=merged_attempt_metadata,
                reason_code=REASON_COMPANY_SEARCH_MATCHED,
            )

        if best_candidate.score >= HIGH_CONFIDENCE_SCORE and blocked_reason is not None:
            return self._finalize_review_result(
                lead,
                actor=actor,
                source_provider=best_candidate.candidate.source_provider,
                candidate_summary=candidate_summary,
                candidate_summaries=candidate_summaries,
                reason_code=(
                    REASON_COMPANY_SEARCH_PREVIEW_ONLY
                    if blocked_reason == BLOCKED_REASON_PROVIDER_PREVIEW_MASKED
                    else REASON_COMPANY_SEARCH_NEEDS_REVIEW
                ),
                attempt_metadata=merged_attempt_metadata,
                matched_by="company_search",
                score=best_candidate.score,
                blocked_reason=blocked_reason,
            )

        if self._is_reviewable_company_search_candidate(best_candidate):
            review_reason = blocked_reason or BLOCKED_REASON_BELOW_AUTOFILL_THRESHOLD
            return self._finalize_review_result(
                lead,
                actor=actor,
                source_provider=best_candidate.candidate.source_provider,
                candidate_summary=self._build_candidate_summary(
                    best_candidate,
                    candidate_count=len(scored_candidates),
                    blocked_from_autofill_reason=review_reason,
                    match_confidence=self._review_confidence(best_candidate.score, review_reason),
                ),
                candidate_summaries=candidate_summaries,
                reason_code=(
                    REASON_COMPANY_SEARCH_PREVIEW_ONLY
                    if review_reason == BLOCKED_REASON_PROVIDER_PREVIEW_MASKED
                    else REASON_COMPANY_SEARCH_NEEDS_REVIEW
                ),
                attempt_metadata=merged_attempt_metadata,
                matched_by="company_search",
                score=best_candidate.score,
                blocked_reason=review_reason,
            )

        return self._finalize_missing_cnpj_result(
            lead,
            actor=actor,
            source_provider=best_candidate.candidate.source_provider,
            reason_code=REASON_COMPANY_SEARCH_LOW_CONFIDENCE,
            skipped_reason=COMPANY_SEARCH_LOW_CONFIDENCE_REASON,
            matched_by="company_search",
            candidate_summary=candidate_summary,
            candidate_summaries=candidate_summaries,
            attempt_metadata=merged_attempt_metadata,
        )

    def _enrich_missing_cnpj_via_cnpja_commercial(
        self,
        lead,
        *,
        evidence_profile: _EvidenceProfile,
        actor: str,
        errors: list[str],
        attempt_metadata: dict[str, Any] | None,
        search_mode: str,
        force_paid_search: bool,
    ) -> CNPJEnrichmentRunResult:
        provider = "cnpja_commercial"
        attempt_plans = self._build_cnpja_commercial_attempts(evidence_profile, search_mode=search_mode)
        search_attempts: list[dict[str, Any]] = []
        candidates_by_cnpj: dict[str, CNPJLookupResult] = {}
        executed_calls = 0
        duplicate_skips = 0
        recent_skips = 0

        for attempt_plan in attempt_plans:
            if executed_calls >= self._max_paid_calls_for_mode(search_mode):
                break
            if not self._should_execute_attempt_plan(
                attempt_plan,
                evidence_profile=evidence_profile,
                current_candidates=candidates_by_cnpj,
            ):
                continue

            signature_payload = self._build_attempt_signature_payload(
                evidence_profile=evidence_profile,
                provider=provider,
                attempt_plan=attempt_plan,
                search_mode=search_mode,
            )
            signature = self._build_company_search_signature(signature_payload)
            if signature in self._paid_search_signature_cache:
                duplicate_skips += 1
                self._paid_calls_skipped_duplicate += 1
                search_attempts.append(
                    self._build_skipped_attempt_metadata(
                        attempt_plan,
                        signature=signature,
                        signature_payload=signature_payload,
                        status="skipped_duplicate",
                    )
                )
                continue

            recent_entry = None
            if not force_paid_search:
                recent_entry = self._find_recent_paid_search_entry(lead, signature=signature, provider=provider)
            if recent_entry is not None:
                recent_skips += 1
                self._paid_calls_skipped_recent += 1
                search_attempts.append(
                    self._build_skipped_attempt_metadata(
                        attempt_plan,
                        signature=signature,
                        signature_payload=signature_payload,
                        status="skipped_recent",
                        recent_entry=recent_entry,
                    )
                )
                continue

            try:
                matches, provider_attempt = self.provider.execute_commercial_search_attempt(
                    mode=attempt_plan.mode,
                    label=attempt_plan.label,
                    query_param=attempt_plan.query_param,
                    searched_values=attempt_plan.searched_values,
                    params=attempt_plan.params,
                    reason=attempt_plan.reason,
                )
            except CNPJAProviderError as exc:
                reason_code = self._provider_reason_code(str(exc), company_search=True)
                if reason_code == REASON_COMPANY_SEARCH_RATE_LIMITED and self.settings.cnpja_stop_batch_on_rate_limit:
                    self._company_search_rate_limited_in_batch = True
                error_attempt_metadata = self._merge_attempt_metadata(
                    attempt_metadata,
                    self._build_company_search_attempt_metadata(
                        evidence_profile=evidence_profile,
                        provider=provider,
                        search_mode=search_mode,
                        search_attempts=[
                            *search_attempts,
                            self._build_skipped_attempt_metadata(
                                attempt_plan,
                                signature=signature,
                                signature_payload=signature_payload,
                                status="provider_error",
                                error_message=str(exc),
                            ),
                        ],
                        candidates_returned_count=len(candidates_by_cnpj),
                        actual_request_made=executed_calls > 0,
                        paid_calls_made=executed_calls,
                        paid_calls_skipped_duplicate=duplicate_skips,
                        paid_calls_skipped_recent=recent_skips,
                    ),
                )
                return self._record_error(
                    lead,
                    actor=actor,
                    error_message=str(exc),
                    errors=errors,
                    source_provider=provider,
                    reason_code=reason_code,
                    attempt_metadata=error_attempt_metadata,
                )

            executed_calls += 1
            self._paid_calls_made += 1
            self._paid_search_signature_cache.add(signature)
            search_attempts.append(
                {
                    **provider_attempt,
                    "status": "executed",
                    "query_signature": signature,
                    "signature_payload": signature_payload,
                    "searched_email_domain_source": attempt_plan.domain_source,
                }
            )
            for candidate in matches:
                candidates_by_cnpj.setdefault(candidate.cnpj, candidate)

        company_search_metadata = self._build_company_search_attempt_metadata(
            evidence_profile=evidence_profile,
            provider=provider,
            search_mode=search_mode,
            search_attempts=search_attempts,
            candidates_returned_count=len(candidates_by_cnpj),
            actual_request_made=executed_calls > 0,
            paid_calls_made=executed_calls,
            paid_calls_skipped_duplicate=duplicate_skips,
            paid_calls_skipped_recent=recent_skips,
        )
        merged_attempt_metadata = self._merge_attempt_metadata(attempt_metadata, company_search_metadata)

        if not candidates_by_cnpj:
            if recent_skips > 0 and executed_calls == 0:
                return self._build_recent_paid_search_skip_result_from_attempts(
                    lead,
                    actor=actor,
                    attempt_metadata=merged_attempt_metadata,
                )
            return self._finalize_missing_cnpj_result(
                lead,
                actor=actor,
                source_provider=provider,
                reason_code=REASON_CNPJA_ZERO_CANDIDATES,
                skipped_reason=CNPJA_ZERO_CANDIDATES_REASON,
                attempt_metadata=merged_attempt_metadata,
            )

        scored_candidates = sorted(
            (self._score_candidate(evidence_profile, candidate) for candidate in candidates_by_cnpj.values()),
            key=lambda item: item.score,
            reverse=True,
        )
        best_candidate = scored_candidates[0]
        top_gap = (
            best_candidate.score - scored_candidates[1].score
            if len(scored_candidates) > 1
            else CLEAR_WINNER_GAP
        )
        blocked_reason = self._blocked_from_autofill_reason(
            best_candidate,
            top_gap=top_gap,
            require_confirmable_cnpj=True,
        )
        candidate_summary = self._build_candidate_summary(
            best_candidate,
            candidate_count=len(scored_candidates),
            blocked_from_autofill_reason=blocked_reason,
            match_confidence=(
                self._review_confidence(best_candidate.score, blocked_reason)
                if blocked_reason
                else self._score_to_confidence(best_candidate.score)
            ),
        )
        candidate_summaries = self._build_candidate_summaries(
            scored_candidates,
            best_score=best_candidate.score,
            prefer_strong_only=blocked_reason == BLOCKED_REASON_AMBIGUOUS_TOP_CANDIDATES,
        )
        merged_attempt_metadata = self._attach_company_search_candidate_diagnostics(
            merged_attempt_metadata,
            best_candidate=best_candidate,
            candidate_summary=candidate_summary,
            candidates_returned_count=len(scored_candidates),
            rejection_reason=self._top_candidate_rejection_reason(
                best_candidate,
                blocked_reason=blocked_reason,
            ),
        )

        if self._is_high_confidence_match(best_candidate, top_gap=top_gap) and blocked_reason is None:
            return self._apply_lookup_result(
                lead,
                best_candidate.candidate,
                actor=actor,
                match_confidence=self._score_to_confidence(best_candidate.score),
                matched_by="company_search",
                candidate_summary=candidate_summary,
                candidate_summaries=candidate_summaries,
                attempt_metadata=merged_attempt_metadata,
                reason_code=REASON_COMPANY_SEARCH_MATCHED,
            )

        if best_candidate.score >= HIGH_CONFIDENCE_SCORE and blocked_reason is not None:
            return self._finalize_review_result(
                lead,
                actor=actor,
                source_provider=best_candidate.candidate.source_provider,
                candidate_summary=candidate_summary,
                candidate_summaries=candidate_summaries,
                reason_code=REASON_COMPANY_SEARCH_NEEDS_REVIEW,
                attempt_metadata=merged_attempt_metadata,
                matched_by="company_search",
                score=best_candidate.score,
                blocked_reason=blocked_reason,
            )

        if self._is_reviewable_company_search_candidate(best_candidate):
            review_reason = blocked_reason or BLOCKED_REASON_BELOW_AUTOFILL_THRESHOLD
            return self._finalize_review_result(
                lead,
                actor=actor,
                source_provider=best_candidate.candidate.source_provider,
                candidate_summary=self._build_candidate_summary(
                    best_candidate,
                    candidate_count=len(scored_candidates),
                    blocked_from_autofill_reason=review_reason,
                    match_confidence=self._review_confidence(best_candidate.score, review_reason),
                ),
                candidate_summaries=candidate_summaries,
                reason_code=REASON_COMPANY_SEARCH_NEEDS_REVIEW,
                attempt_metadata=merged_attempt_metadata,
                matched_by="company_search",
                score=best_candidate.score,
                blocked_reason=review_reason,
            )

        return self._finalize_missing_cnpj_result(
            lead,
            actor=actor,
            source_provider=best_candidate.candidate.source_provider,
            reason_code=REASON_COMPANY_SEARCH_LOW_CONFIDENCE,
            skipped_reason=COMPANY_SEARCH_LOW_CONFIDENCE_REASON,
            matched_by="company_search",
            candidate_summary=candidate_summary,
            candidate_summaries=candidate_summaries,
            attempt_metadata=merged_attempt_metadata,
        )

    def _build_cnpja_commercial_attempts(
        self,
        evidence_profile: _EvidenceProfile,
        *,
        search_mode: str,
    ) -> list[_CommercialAttemptPlan]:
        limit_10 = str(min(max(1, self.settings.cnpja_company_search_limit), 10))
        location_params = self._base_cnpja_location_params(evidence_profile, limit=limit_10)
        attempts: list[_CommercialAttemptPlan] = []

        searchable_domain = evidence_profile.searchable_email_domain
        searchable_domain_source = evidence_profile.searchable_email_domain_source
        if search_mode in {"balanced", "delivery"} and searchable_domain and self.settings.cnpja_enable_email_domain_search:
            attempts.append(
                _CommercialAttemptPlan(
                    mode="email_domain",
                    label="Domínio/email",
                    reason="Strong company-owned domain evidence.",
                    query_param="emails.domain.in",
                    searched_values=[searchable_domain],
                    domain_source=searchable_domain_source,
                    params={
                        **location_params,
                        "emails.domain.in": searchable_domain,
                    },
                )
            )

        if evidence_profile.alias_variants:
            attempts.append(
                _CommercialAttemptPlan(
                    mode="alias",
                    label="Nome fantasia",
                    reason="Public brand/fantasy-name search.",
                    query_param="alias.in",
                    searched_values=evidence_profile.alias_variants,
                    params={
                        **location_params,
                        "alias.in": ",".join(evidence_profile.alias_variants),
                    },
                )
            )

        if search_mode in {"balanced", "delivery"} and evidence_profile.names_variants:
            params = dict(location_params)
            params["names.in"] = ",".join(evidence_profile.names_variants)
            if evidence_profile.phone_area:
                params["phones.area.in"] = evidence_profile.phone_area
            attempts.append(
                _CommercialAttemptPlan(
                    mode="names",
                    label="Razão/nome fantasia",
                    reason="Broader establishment-name search after alias/domain evidence.",
                    query_param="names.in",
                    searched_values=evidence_profile.names_variants,
                    params=params,
                    run_condition="if_no_reviewable_candidate",
                )
            )

        if (
            search_mode == "delivery"
            and self.settings.cnpja_enable_zip_fallback
            and evidence_profile.postal_code
            and evidence_profile.state
        ):
            attempts.append(
                _CommercialAttemptPlan(
                    mode="zip_fallback",
                    label="Busca por CEP",
                    reason="Location-only fallback when marketing names do not match Receita aliases.",
                    query_param=None,
                    searched_values=[evidence_profile.postal_code],
                    params={
                        **self._base_cnpja_location_params(evidence_profile, limit="20"),
                        "address.zip.in": evidence_profile.postal_code,
                    },
                    run_condition="if_no_reviewable_candidate",
                )
            )

        if (
            search_mode == "delivery"
            and self.settings.cnpja_enable_strict_address_attempt
            and evidence_profile.postal_code
            and evidence_profile.neighborhood
            and (evidence_profile.alias_variants or evidence_profile.names_variants)
        ):
            strict_query_param = "alias.in" if evidence_profile.alias_variants else "names.in"
            strict_values = evidence_profile.alias_variants[:2] or evidence_profile.names_variants[:2]
            strict_params = {
                **self._base_cnpja_location_params(evidence_profile, limit=limit_10),
                strict_query_param: ",".join(strict_values),
                "address.zip.in": evidence_profile.postal_code,
                "address.district.in": evidence_profile.neighborhood,
            }
            if self.settings.cnpja_use_email_domain_filter and searchable_domain:
                strict_params["emails.domain.in"] = searchable_domain
            attempts.append(
                _CommercialAttemptPlan(
                    mode="address",
                    label="Busca com endereço",
                    reason="Strict address confirmation attempt for delivery mode.",
                    query_param=strict_query_param,
                    searched_values=strict_values,
                    params=strict_params,
                    run_condition="if_no_reviewable_candidate",
                )
            )

        if (
            search_mode == "delivery"
            and self.settings.cnpja_enable_legal_name_attempt
            and evidence_profile.legal_name_variants
            and self._looks_legal_company_name(evidence_profile.business_name)
        ):
            attempts.append(
                _CommercialAttemptPlan(
                    mode="company_name",
                    label="Razão social",
                    reason="Legal-name search for company-like business names.",
                    query_param="company.name.in",
                    searched_values=evidence_profile.legal_name_variants,
                    params={
                        **location_params,
                        "company.name.in": ",".join(evidence_profile.legal_name_variants),
                    },
                    run_condition="if_no_reviewable_candidate",
                )
            )

        deduped: list[_CommercialAttemptPlan] = []
        seen_params: set[str] = set()
        max_attempts = min(
            self._max_paid_calls_for_mode(search_mode),
            max(1, self.settings.cnpja_max_search_attempts_per_lead),
        )
        for attempt in attempts:
            encoded = json.dumps(attempt.params, sort_keys=True, ensure_ascii=True)
            if encoded in seen_params:
                continue
            seen_params.add(encoded)
            deduped.append(attempt)
            if len(deduped) >= max_attempts:
                break
        return deduped

    def _base_cnpja_location_params(self, evidence_profile: _EvidenceProfile, *, limit: str) -> dict[str, str]:
        params = {
            "limit": limit,
            "status.id.in": "2",
        }
        if evidence_profile.state:
            params["address.state.in"] = evidence_profile.state
        if evidence_profile.municipality_ibge_code:
            params["address.municipality.in"] = evidence_profile.municipality_ibge_code
        return params

    def _resolve_searchable_domain(self, evidence_profile: _EvidenceProfile) -> str | None:
        return evidence_profile.searchable_email_domain

    def _max_paid_calls_for_mode(self, search_mode: str) -> int:
        configured = max(1, self.settings.cnpja_max_paid_calls_per_lead)
        if search_mode == "cheap":
            return min(configured, 1)
        if search_mode == "balanced":
            return min(configured, 2)
        return min(configured, 4)

    def _should_execute_attempt_plan(
        self,
        attempt_plan: _CommercialAttemptPlan,
        *,
        evidence_profile: _EvidenceProfile,
        current_candidates: dict[str, CNPJLookupResult],
    ) -> bool:
        if attempt_plan.run_condition == "always":
            return True
        if attempt_plan.run_condition == "if_no_reviewable_candidate":
            if not current_candidates:
                return True
            scored_candidates = [
                self._score_candidate(evidence_profile, candidate)
                for candidate in current_candidates.values()
            ]
            return max((candidate.score for candidate in scored_candidates), default=0) < REVIEWABLE_COMPANY_SEARCH_SCORE
        return not current_candidates

    def _build_attempt_signature_payload(
        self,
        *,
        evidence_profile: _EvidenceProfile,
        provider: str,
        attempt_plan: _CommercialAttemptPlan,
        search_mode: str,
    ) -> dict[str, Any]:
        return {
            "provider": provider,
            "endpoint": "/office",
            "mode": attempt_plan.mode,
            "query_param": attempt_plan.query_param,
            "params": attempt_plan.params,
        }

    def _build_skipped_attempt_metadata(
        self,
        attempt_plan: _CommercialAttemptPlan,
        *,
        signature: str,
        signature_payload: dict[str, Any],
        status: str,
        recent_entry: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        metadata = {
            "query_mode": attempt_plan.mode,
            "query_mode_label": attempt_plan.label,
            "query_param": attempt_plan.query_param,
            "searched_values": attempt_plan.searched_values,
            "searched_email_domain_source": attempt_plan.domain_source,
            "candidate_count": 0,
            "candidates_returned_count": 0,
            "reason": attempt_plan.reason,
            "provider_status": status,
            "params_sent": dict(attempt_plan.params),
            "query_signature": signature,
            "signature_payload": signature_payload,
        }
        if recent_entry is not None:
            metadata["last_attempt_at"] = recent_entry.get("timestamp")
            metadata["last_result_status"] = recent_entry.get("result_status")
            metadata["last_candidates_count"] = recent_entry.get("candidate_count")
        if error_message:
            metadata["error_message"] = error_message
        return metadata

    def _build_company_search_attempt_metadata(
        self,
        *,
        evidence_profile: _EvidenceProfile,
        provider: str,
        search_mode: str,
        search_attempts: list[dict[str, Any]],
        candidates_returned_count: int,
        actual_request_made: bool,
        paid_calls_made: int,
        paid_calls_skipped_duplicate: int,
        paid_calls_skipped_recent: int,
    ) -> dict[str, Any]:
        return {
            "provider": provider,
            "search_mode": search_mode,
            "searched_city": evidence_profile.city,
            "searched_state": evidence_profile.state,
            "searched_municipality_code": evidence_profile.municipality_ibge_code,
            "municipality_mapping_found": evidence_profile.municipality_ibge_code is not None,
            "searched_zip": evidence_profile.postal_code,
            "searched_district": evidence_profile.neighborhood,
            "raw_phone_area": evidence_profile.raw_phone_area,
            "searched_phone_area": evidence_profile.phone_area,
            "expected_phone_area": evidence_profile.expected_phone_area,
            "phone_area_conflict": evidence_profile.phone_area_conflict,
            "searched_email_domain": evidence_profile.searchable_email_domain,
            "searched_email_domain_source": evidence_profile.searchable_email_domain_source,
            "searched_alias_names": evidence_profile.alias_variants,
            "searched_names": evidence_profile.names_variants,
            "searched_legal_names": evidence_profile.legal_name_variants,
            "search_attempts": search_attempts,
            "search_attempts_count": len(search_attempts),
            "candidates_returned_count": candidates_returned_count,
            "actual_request_made": actual_request_made,
            "paid_calls_made": paid_calls_made,
            "paid_calls_skipped_duplicate": paid_calls_skipped_duplicate,
            "paid_calls_skipped_recent": paid_calls_skipped_recent,
            "cnpja_zero_candidates": candidates_returned_count == 0 and actual_request_made,
            "evidence_profile": evidence_profile.to_summary(),
            "extracted_zip_from_address": evidence_profile.extracted_zip_from_address,
        }

    def _find_recent_paid_search_entry(
        self,
        lead,
        *,
        signature: str,
        provider: str,
    ) -> dict[str, Any] | None:
        cooldown = timedelta(hours=max(1, self.settings.cnpj_paid_search_repeat_cooldown_hours))
        metadata = lead.cnpj_metadata_json or {}
        attempts = metadata.get("cnpj_paid_search_last_attempts")
        if isinstance(attempts, list):
            for item in reversed(attempts):
                if not isinstance(item, dict):
                    continue
                if item.get("signature") != signature or item.get("provider") != provider:
                    continue
                result_status = item.get("result_status")
                timestamp = self._parse_metadata_datetime(item.get("timestamp"))
                if (
                    not isinstance(result_status, str)
                    or result_status not in PAID_SEARCH_REPEATABLE_REASON_CODES
                    or timestamp is None
                ):
                    continue
                if utcnow() - timestamp < cooldown:
                    return dict(item)

        if self._should_skip_recent_paid_search(lead, signature=signature, provider=provider):
            return {
                "signature": signature,
                "provider": provider,
                "timestamp": metadata.get("cnpj_paid_search_last_attempt_at"),
                "result_status": metadata.get("cnpj_paid_search_last_result_status"),
                "candidate_count": metadata.get("cnpj_paid_search_last_candidates_count"),
            }
        return None

    def _build_recent_paid_search_skip_result_from_attempts(
        self,
        lead,
        *,
        actor: str,
        attempt_metadata: dict[str, Any] | None,
    ) -> CNPJEnrichmentRunResult:
        match_status = getattr(lead, "cnpj_match_status", None) or "unknown"
        candidate_summary = self._get_candidate_summary_if_present(lead)
        self._mark_attempt(
            lead,
            actor=actor,
            match_status=match_status,
            match_confidence=lead.cnpj_match_confidence,
            source_provider=lead.cnpj_source_provider or self._company_search_source_provider(),
            skipped_reason=PAID_SEARCH_RECENTLY_ATTEMPTED_REASON,
            error_message=None,
            reason_code=REASON_PAID_SEARCH_RECENTLY_ATTEMPTED,
            attempt_metadata=attempt_metadata,
            candidate_summary=candidate_summary,
        )
        return CNPJEnrichmentRunResult(
            lead_id=lead.id,
            business_name=lead.business_name,
            success=True,
            cnpj=lead.cnpj,
            legal_name=lead.legal_name,
            match_status=match_status,
            match_confidence=lead.cnpj_match_confidence,
            reason_code=REASON_PAID_SEARCH_RECENTLY_ATTEMPTED,
            skipped_reason=PAID_SEARCH_RECENTLY_ATTEMPTED_REASON,
            last_enriched_at=lead.cnpj_last_enriched_at,
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
        blocked_reason = self._blocked_from_autofill_reason(
            best_candidate,
            top_gap=top_gap,
            require_confirmable_cnpj=True,
        )
        candidate_summary = self._build_candidate_summary(
            best_candidate,
            candidate_count=len(validated_candidates),
            blocked_from_autofill_reason=blocked_reason,
            match_confidence=(
                self._review_confidence(best_candidate.score, blocked_reason)
                if blocked_reason
                else self._score_to_confidence(best_candidate.score)
            ),
        )
        candidate_summaries = self._build_candidate_summaries(
            validated_candidates,
            best_score=best_candidate.score,
            prefer_strong_only=blocked_reason == BLOCKED_REASON_AMBIGUOUS_TOP_CANDIDATES,
        )

        if self._is_high_confidence_match(best_candidate, top_gap=top_gap) and blocked_reason is None:
            return _WebsiteEvaluationOutcome(
                final_result=self._apply_lookup_result(
                    lead,
                    best_candidate.candidate,
                    actor=actor,
                    match_confidence=self._score_to_confidence(best_candidate.score),
                    matched_by="website_cnpj",
                    candidate_summary=candidate_summary,
                    candidate_summaries=candidate_summaries,
                    attempt_metadata=extraction.attempt_metadata,
                ),
                attempt_metadata=extraction.attempt_metadata,
            )

        if best_candidate.score >= MEDIUM_CONFIDENCE_SCORE and not self._has_location_conflict(best_candidate):
            review_reason = blocked_reason or BLOCKED_REASON_BELOW_AUTOFILL_THRESHOLD
            return _WebsiteEvaluationOutcome(
                final_result=self._finalize_review_result(
                    lead,
                    actor=actor,
                    source_provider=best_candidate.candidate.source_provider,
                    candidate_summary=self._build_candidate_summary(
                        best_candidate,
                        candidate_count=len(validated_candidates),
                        blocked_from_autofill_reason=review_reason,
                        match_confidence=self._review_confidence(best_candidate.score, review_reason),
                    ),
                    candidate_summaries=candidate_summaries,
                    reason_code=REASON_NEEDS_REVIEW,
                    attempt_metadata=extraction.attempt_metadata,
                    matched_by="website_cnpj",
                    score=best_candidate.score,
                    blocked_reason=review_reason,
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
        candidate_summaries: list[dict[str, Any]] | None = None,
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
            candidate_summaries=candidate_summaries,
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
    def _with_company_search_request_metadata(
        provider_attempt_metadata: dict[str, Any] | None,
        *,
        query_signature: str,
        signature_payload: dict[str, Any],
        provider: str,
        actual_request_made: bool,
    ) -> dict[str, Any]:
        merged = dict(provider_attempt_metadata or {})
        merged["provider"] = provider
        merged["query_signature"] = query_signature
        merged["signature_payload"] = signature_payload
        merged["actual_request_made"] = actual_request_made
        return merged

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
    def _attach_company_search_candidate_diagnostics(
        attempt_metadata: dict[str, Any] | None,
        *,
        best_candidate: _ScoredCandidate,
        candidate_summary: dict[str, Any],
        candidates_returned_count: int,
        rejection_reason: str | None,
    ) -> dict[str, Any]:
        merged = dict(attempt_metadata or {})
        company_search_metadata = dict(merged.get("company_search") or {})
        company_search_metadata["candidates_returned_count"] = candidates_returned_count
        company_search_metadata["top_candidate_score"] = best_candidate.score
        company_search_metadata["top_candidate_rejection_reason"] = rejection_reason
        company_search_metadata["top_candidate_summary"] = candidate_summary
        merged["company_search"] = company_search_metadata
        return merged

    @staticmethod
    def _top_candidate_rejection_reason(
        candidate: _ScoredCandidate,
        *,
        blocked_reason: str | None,
    ) -> str | None:
        if blocked_reason:
            return blocked_reason
        if candidate.score < MEDIUM_CONFIDENCE_SCORE:
            return "below_review_threshold"
        if candidate.score < HIGH_CONFIDENCE_SCORE:
            return BLOCKED_REASON_BELOW_AUTOFILL_THRESHOLD
        return None

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
            alias_match=strong_name_match,
            legal_name_match=False,
            person_like_legal_name=self._looks_person_like_legal_name(lookup.legal_name),
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
        candidate_summaries: list[dict[str, Any]] | None = None,
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
            candidate_summaries=candidate_summaries,
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
        candidate_summaries: list[dict[str, Any]] | None = None,
    ) -> None:
        attempted_at = utcnow()
        lead.cnpj_match_status = match_status
        lead.cnpj_match_confidence = match_confidence
        lead.cnpj_last_enriched_at = attempted_at
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
            candidate_summaries=candidate_summaries,
            attempted_at=attempted_at,
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
                    "candidate_summaries": candidate_summaries,
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

    def _score_candidate(self, lead_or_profile, candidate: CNPJLookupResult) -> _ScoredCandidate:
        profile = lead_or_profile if isinstance(lead_or_profile, _EvidenceProfile) else self._build_evidence_profile(lead_or_profile)
        evidence: dict[str, int] = {}
        penalties: list[str] = []
        score = 0

        profile_domains = {
            value
            for value in (profile.website_domain, profile.email_domain)
            if value
        }
        candidate_domains = {
            value
            for value in (
                candidate.domain,
                normalize_domain(candidate.website),
                *(
                    value
                    for value in (candidate.metadata or {}).get("email_domains", [])
                    if isinstance(value, str)
                ),
            )
            if value
        }
        if profile_domains and candidate_domains and profile_domains.intersection(candidate_domains):
            evidence["domain_or_email"] = 40
            score += 40

        lead_numbers = set(profile.phone_digits)
        candidate_numbers = {
            value for value in (normalize_phone_br(phone) for phone in candidate.phones) if value
        }
        if lead_numbers and candidate_numbers and lead_numbers.intersection(candidate_numbers):
            evidence["phone"] = 35
            score += 35
        elif profile.phone_area:
            candidate_areas = {
                self._extract_area_code(phone)
                for phone in candidate.phones
            }
            if profile.phone_area in candidate_areas:
                evidence["phone_area"] = 5
                score += 5

        lead_name = normalize_business_name(profile.business_name)
        strong_name_match = False
        alias_match = False
        legal_name_match = False
        candidate_alias = normalize_business_name(candidate.trade_name)
        candidate_legal_name = normalize_business_name(candidate.legal_name)
        normalized_alias_variants = [normalize_business_name(value) for value in profile.alias_variants if normalize_business_name(value)]
        normalized_name_variants = [normalize_business_name(value) for value in profile.names_variants if normalize_business_name(value)]
        if normalized_alias_variants and candidate_alias:
            if candidate_alias in normalized_alias_variants:
                evidence["alias_name"] = 25
                score += 25
                strong_name_match = True
                alias_match = True
            elif any(self._is_strong_name_variant(variant, candidate_alias) for variant in normalized_alias_variants):
                evidence["alias_name"] = 20
                score += 20
                alias_match = True
                strong_name_match = True

        brand_tokens = self._brand_tokens(profile.brand_variants or [profile.business_name])
        if brand_tokens and candidate_legal_name and brand_tokens.issubset(set(candidate_legal_name.split())):
            evidence["brand_in_legal_name"] = 15
            score += 15
            legal_name_match = True
        elif brand_tokens and candidate_legal_name and brand_tokens.intersection(set(candidate_legal_name.split())):
            evidence["brand_in_legal_name"] = 10
            score += 10
            legal_name_match = True

        if lead_name and candidate_legal_name and not alias_match:
            if lead_name == candidate_legal_name:
                evidence["legal_name"] = 15
                score += 15
                strong_name_match = True
                legal_name_match = True
            elif self._is_strong_name_variant(lead_name, candidate_legal_name):
                evidence["legal_name"] = 12
                score += 12
                legal_name_match = True

        lead_street, lead_number = profile.street_name, profile.address_number
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
        if lead_number and candidate_number and lead_number == candidate_number:
            evidence["address_number"] = 10
            score += 10
        elif lead_number and candidate_number and lead_number != candidate_number:
            score -= 10
            penalties.append("different_number")

        lead_postal = profile.postal_code
        candidate_postal = self._normalize_postal_code(candidate.postal_code)
        if lead_postal and candidate_postal and lead_postal == candidate_postal:
            evidence["postal_code"] = 25
            score += 25

        lead_neighborhood = normalize_text(profile.neighborhood)
        candidate_neighborhood = normalize_text(
            (candidate.metadata or {}).get("neighborhood")
            if isinstance((candidate.metadata or {}).get("neighborhood"), str)
            else None
        )
        if lead_neighborhood and candidate_neighborhood and lead_neighborhood == candidate_neighborhood:
            evidence["neighborhood"] = 10
            score += 10

        lead_city = normalize_text(profile.city)
        candidate_city = normalize_text(candidate.city)
        if lead_city and candidate_city:
            if lead_city == candidate_city:
                evidence["city"] = 15
                score += 15
            else:
                score -= 30
                penalties.append("different_city")

        lead_state = normalize_brazilian_state(profile.state) or normalize_text(profile.state)
        candidate_state = normalize_brazilian_state(candidate.state) or normalize_text(candidate.state)
        if lead_state and candidate_state:
            if lead_state == candidate_state:
                evidence["state"] = 10
                score += 10
            else:
                score -= 40
                penalties.append("different_state")

        candidate_main_activity_id = None
        if isinstance(candidate.metadata, dict):
            raw_activity_id = candidate.metadata.get("main_activity_id")
            if isinstance(raw_activity_id, str):
                candidate_main_activity_id = raw_activity_id
        if category_activity_matches(
            profile.category,
            primary_activity=candidate.primary_activity,
            main_activity_id=candidate_main_activity_id,
        ):
            evidence["activity"] = 8
            score += 8

        if not alias_match and not legal_name_match and brand_tokens and candidate_alias:
            candidate_alias_tokens = set(candidate_alias.split())
            if brand_tokens.intersection(candidate_alias_tokens):
                evidence["brand_in_alias"] = 15
                score += 15
                alias_match = True

        supportive_signal_count = sum(
            1
            for key in (
                "domain_or_email",
                "phone",
                "address",
                "address_number",
                "postal_code",
                "neighborhood",
            )
            if key in evidence
        )
        if not (alias_match or legal_name_match) and "domain_or_email" not in evidence and "phone" not in evidence:
            penalties.append("weak_name_support")
        person_like_legal_name = self._looks_person_like_legal_name(candidate.legal_name)
        return _ScoredCandidate(
            candidate=candidate,
            score=max(score, 0),
            evidence=evidence,
            penalties=penalties,
            strong_name_match=strong_name_match,
            alias_match=alias_match,
            legal_name_match=legal_name_match,
            person_like_legal_name=person_like_legal_name,
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
    def _brand_tokens(variants: list[str]) -> set[str]:
        tokens: set[str] = set()
        for variant in variants:
            normalized = normalize_text(variant)
            if not normalized:
                continue
            for token in normalized.split():
                if len(token) >= 4 and token not in {"loja", "shop", "casa", "material", "construcao"}:
                    tokens.add(token)
        return tokens

    @staticmethod
    def _looks_legal_company_name(value: str | None) -> bool:
        normalized = normalize_text(value)
        if normalized is None:
            return False
        tokens = set(normalized.split())
        return bool(
            tokens.intersection(
                {"ltda", "me", "mei", "eireli", "comercio", "servicos", "industria", "materiais", "construcao"}
            )
        )

    @staticmethod
    def _looks_person_like_legal_name(value: str | None) -> bool:
        normalized = normalize_text(value)
        if not normalized:
            return False
        company_terms = {"ltda", "me", "mei", "eireli", "sa", "s a", "comercio", "servicos", "industria"}
        tokens = normalized.split()
        if any(token in company_terms for token in tokens):
            return False
        return 2 <= len(tokens) <= 5 and all(token.isalpha() for token in tokens)

    @staticmethod
    def _normalize_postal_code(value: str | None) -> str | None:
        if not value:
            return None
        digits = "".join(character for character in value if character.isdigit())
        return digits or None

    @staticmethod
    def _extract_postal_code_from_text(value: str | None) -> str | None:
        if not value:
            return None
        match = _ZIP_PATTERN.search(value)
        if not match:
            return None
        return f"{match.group(1)}{match.group(2)}"

    @staticmethod
    def _extract_address_number_from_text(value: str | None) -> str | None:
        if not value:
            return None
        match = re.search(r"(?:,\s*|\s+-\s*)(\d+[A-Za-z0-9/-]*)\b", value)
        if not match:
            return None
        candidate = match.group(1).strip()
        return candidate or None

    @staticmethod
    def _extract_area_code(value: str | None) -> str | None:
        if not value:
            return None
        digits = "".join(character for character in value if character.isdigit())
        if len(digits) < 10:
            return None
        return digits[:2] if len(digits) == 10 else digits[-10:-8]

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
        return (
            candidate.score >= HIGH_CONFIDENCE_SCORE
            and top_gap >= CLEAR_WINNER_GAP
            and candidate.supportive_signal_count >= 1
            and (
                candidate.alias_match
                or candidate.legal_name_match
                or "domain_or_email" in candidate.evidence
                or "phone" in candidate.evidence
                or "postal_code" in candidate.evidence
                or "address" in candidate.evidence
            )
            and not self._has_location_conflict(candidate)
        )

    def _is_reviewable_company_search_candidate(self, candidate: _ScoredCandidate) -> bool:
        if self._has_location_conflict(candidate):
            return False
        if candidate.score < REVIEWABLE_COMPANY_SEARCH_SCORE:
            return False
        if not self._candidate_has_confirmable_cnpj(candidate):
            return False
        return self._candidate_supports_manual_approval(candidate)

    def _candidate_supports_manual_approval(self, candidate: _ScoredCandidate) -> bool:
        if not self._candidate_has_confirmable_cnpj(candidate):
            return False
        has_name_support = candidate.alias_match or candidate.legal_name_match or candidate.strong_name_match
        has_location_support = "city" in candidate.evidence and "state" in candidate.evidence
        has_identity_support = any(
            key in candidate.evidence
            for key in ("domain_or_email", "phone", "postal_code", "address", "address_number", "neighborhood")
        )
        return (has_location_support and has_name_support) or has_identity_support

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

    def _review_confidence(self, score: int, blocked_reason: str | None) -> float:
        confidence = self._score_to_confidence(score)
        if blocked_reason:
            return confidence
        if confidence >= self._score_to_confidence(HIGH_CONFIDENCE_SCORE):
            return self._score_to_confidence(HIGH_CONFIDENCE_SCORE - 1)
        return confidence

    @staticmethod
    def _has_location_conflict(candidate: _ScoredCandidate) -> bool:
        return any(penalty in {"different_city", "different_state"} for penalty in candidate.penalties)

    def _blocked_from_autofill_reason(
        self,
        candidate: _ScoredCandidate,
        *,
        top_gap: int,
        require_confirmable_cnpj: bool,
    ) -> str | None:
        if self._has_location_conflict(candidate):
            return BLOCKED_REASON_CITY_STATE_CONFLICT
        if top_gap < CLEAR_WINNER_GAP:
            return BLOCKED_REASON_AMBIGUOUS_TOP_CANDIDATES
        if candidate.supportive_signal_count < 1 and not (candidate.alias_match or candidate.legal_name_match):
            return BLOCKED_REASON_INSUFFICIENT_IDENTITY_SUPPORT
        if require_confirmable_cnpj and not self._candidate_has_confirmable_cnpj(candidate):
            metadata = candidate.candidate.metadata or {}
            if metadata.get("preview_mode"):
                return BLOCKED_REASON_PROVIDER_PREVIEW_MASKED
            return BLOCKED_REASON_MISSING_FULL_CNPJ
        return None

    @staticmethod
    def _review_reason_text(blocked_reason: str | None) -> str | None:
        if blocked_reason == BLOCKED_REASON_MISSING_FULL_CNPJ:
            return "O provedor não retornou um CNPJ completo para confirmação automática."
        if blocked_reason == BLOCKED_REASON_CITY_STATE_CONFLICT:
            return "Cidade ou UF do candidato conflita com o lead."
        if blocked_reason == BLOCKED_REASON_AMBIGUOUS_TOP_CANDIDATES:
            return "Mais de um candidato forte foi encontrado."
        if blocked_reason == BLOCKED_REASON_PROVIDER_PREVIEW_MASKED:
            return "O provedor retornou dados em modo prévia ou mascarados."
        if blocked_reason == BLOCKED_REASON_INSUFFICIENT_IDENTITY_SUPPORT:
            return "Os sinais de identidade ainda não são suficientes para preencher automaticamente."
        if blocked_reason == BLOCKED_REASON_BELOW_AUTOFILL_THRESHOLD:
            return "O candidato ficou abaixo do limite de confirmação automática."
        return None

    def _build_candidate_summary(
        self,
        candidate: _ScoredCandidate,
        *,
        candidate_count: int,
        blocked_from_autofill_reason: str | None = None,
        match_confidence: float | None = None,
    ) -> dict[str, Any]:
        candidate_metadata = candidate.candidate.metadata or {}
        legal_name_note = None
        if candidate.person_like_legal_name and candidate.alias_match:
            legal_name_note = (
                "Razão social pode ser nome do titular/MEI; confira nome fantasia, endereço e telefone."
            )
        return {
            "cnpj": candidate.candidate.cnpj,
            "legal_name": candidate.candidate.legal_name,
            "trade_name": candidate.candidate.trade_name,
            "address": candidate.candidate.address,
            "city": candidate.candidate.city,
            "state": candidate.candidate.state,
            "postal_code": candidate.candidate.postal_code,
            "website": candidate.candidate.website,
            "domain": candidate.candidate.domain,
            "phones": candidate.candidate.phones,
            "emails": candidate.candidate.emails,
            "registration_status": candidate.candidate.registration_status,
            "primary_activity": candidate.candidate.primary_activity,
            "provider": candidate.candidate.source_provider,
            "score": candidate.score,
            "match_confidence": (
                match_confidence
                if match_confidence is not None
                else CNPJEnrichmentService._score_to_confidence(candidate.score)
            ),
            "evidence": candidate.evidence,
            "penalties": candidate.penalties,
            "candidate_count": candidate_count,
            "source_urls": candidate.source_urls,
            "page_types": candidate.page_types,
            "matched_by": candidate.matched_by,
            "query_mode": candidate_metadata.get("company_search_query_mode"),
            "query_mode_label": candidate_metadata.get("company_search_query_mode_label"),
            "blocked_from_autofill_reason": blocked_from_autofill_reason,
            "review_reason": CNPJEnrichmentService._review_reason_text(blocked_from_autofill_reason),
            "person_like_legal_name": candidate.person_like_legal_name,
            "legal_name_note": legal_name_note,
            "manual_review_approvable": self._candidate_supports_manual_approval(candidate),
        }

    def _build_candidate_summaries(
        self,
        scored_candidates: list[_ScoredCandidate],
        *,
        best_score: int,
        prefer_strong_only: bool = False,
    ) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for candidate in scored_candidates:
            if normalize_cnpj(candidate.candidate.cnpj) is None:
                continue
            if prefer_strong_only and best_score - candidate.score >= CLEAR_WINNER_GAP:
                continue
            if prefer_strong_only and candidate.score < HIGH_CONFIDENCE_SCORE:
                continue
            if not prefer_strong_only and candidate.score < REVIEWABLE_COMPANY_SEARCH_SCORE:
                continue
            if self._has_location_conflict(candidate):
                continue
            blocked_reason = BLOCKED_REASON_BELOW_AUTOFILL_THRESHOLD
            if prefer_strong_only:
                blocked_reason = BLOCKED_REASON_AMBIGUOUS_TOP_CANDIDATES
            summaries.append(
                self._build_candidate_summary(
                    candidate,
                    candidate_count=len(scored_candidates),
                    blocked_from_autofill_reason=blocked_reason,
                    match_confidence=self._review_confidence(candidate.score, blocked_reason),
                )
            )
            if len(summaries) >= 5:
                break
        return summaries

    def _finalize_review_result(
        self,
        lead,
        *,
        actor: str,
        source_provider: str | None,
        candidate_summary: dict[str, Any],
        candidate_summaries: list[dict[str, Any]] | None,
        reason_code: str,
        attempt_metadata: dict[str, Any] | None,
        matched_by: str,
        score: int,
        blocked_reason: str | None,
    ) -> CNPJEnrichmentRunResult:
        confidence = self._review_confidence(score, blocked_reason)
        self._mark_attempt(
            lead,
            actor=actor,
            match_status="needs_review",
            match_confidence=confidence,
            source_provider=source_provider,
            skipped_reason=NEEDS_REVIEW_REASON,
            error_message=None,
            matched_by=matched_by,
            candidate_summary=candidate_summary,
            candidate_summaries=candidate_summaries,
            reason_code=reason_code,
            attempt_metadata=attempt_metadata,
        )
        return CNPJEnrichmentRunResult(
            lead_id=lead.id,
            business_name=lead.business_name,
            success=True,
            cnpj=None,
            legal_name=lead.legal_name,
            match_status="needs_review",
            match_confidence=confidence,
            reason_code=reason_code,
            skipped_reason=NEEDS_REVIEW_REASON,
            last_enriched_at=lead.cnpj_last_enriched_at,
        )

    @staticmethod
    def _candidate_summary_text(candidate_summary: dict[str, Any], key: str) -> str | None:
        value = candidate_summary.get(key)
        if not isinstance(value, str):
            return None
        stripped = value.strip()
        return stripped or None

    @staticmethod
    def _candidate_summary_confidence(
        candidate_summary: dict[str, Any],
        fallback: float | None,
    ) -> float | None:
        value = candidate_summary.get("match_confidence")
        if isinstance(value, (int, float)):
            return max(0.0, min(float(value), 1.0))
        return fallback

    @staticmethod
    def _get_reviewable_candidate_summary(lead) -> dict[str, Any] | None:
        if getattr(lead, "cnpj_match_status", None) != "needs_review":
            return None
        for candidate_summary in CNPJEnrichmentService._get_candidate_summaries_if_present(lead):
            if normalize_cnpj(candidate_summary.get("cnpj")) is not None:
                return dict(candidate_summary)
        return None

    @staticmethod
    def _get_candidate_summaries_if_present(lead) -> list[dict[str, Any]]:
        metadata = lead.cnpj_metadata_json or {}
        candidate_summaries = metadata.get("candidate_summaries")
        normalized: list[dict[str, Any]] = []
        if isinstance(candidate_summaries, list):
            for item in candidate_summaries:
                if isinstance(item, dict):
                    normalized.append(dict(item))
        candidate_summary = metadata.get("candidate_summary")
        if isinstance(candidate_summary, dict):
            primary = dict(candidate_summary)
            primary_cnpj = normalize_cnpj(primary.get("cnpj"))
            if not normalized:
                normalized.append(primary)
            elif primary_cnpj and all(normalize_cnpj(item.get("cnpj")) != primary_cnpj for item in normalized):
                normalized.insert(0, primary)
        return normalized

    @staticmethod
    def _resolve_candidate_summary_for_approval(
        lead,
        *,
        candidate_cnpj: str | None = None,
    ) -> dict[str, Any] | None:
        candidate_summaries = CNPJEnrichmentService._get_candidate_summaries_if_present(lead)
        if not candidate_summaries:
            return None
        if candidate_cnpj is None:
            return dict(candidate_summaries[0])

        normalized_target = normalize_cnpj(candidate_cnpj)
        if normalized_target is None:
            return None
        for candidate_summary in candidate_summaries:
            if normalize_cnpj(candidate_summary.get("cnpj")) == normalized_target:
                return dict(candidate_summary)
        return None

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
        candidate_summaries: list[dict[str, Any]] | None = None,
        attempted_at: datetime | None = None,
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
        if candidate_summaries is not None:
            metadata["candidate_summaries"] = candidate_summaries
        if attempt_metadata is not None:
            metadata["crawl_summary"] = attempt_metadata
            company_search_metadata = attempt_metadata.get("company_search")
            if isinstance(company_search_metadata, dict):
                search_attempts = company_search_metadata.get("search_attempts")
                executed_attempts = [
                    item
                    for item in (search_attempts or [])
                    if isinstance(item, dict) and item.get("status") == "executed"
                ]
                if company_search_metadata.get("evidence_profile") is not None:
                    metadata["evidence_profile_summary"] = company_search_metadata.get("evidence_profile")
                metadata["cnpj_paid_search_candidate_count"] = company_search_metadata.get(
                    "candidates_returned_count",
                    0,
                )
                signatures = [
                    value
                    for value in metadata.get("cnpj_paid_search_signatures", [])
                    if isinstance(value, str)
                ]
                attempts_history = [
                    value
                    for value in metadata.get("cnpj_paid_search_last_attempts", [])
                    if isinstance(value, dict)
                ]
                for executed_attempt in executed_attempts:
                    signature = executed_attempt.get("query_signature")
                    if isinstance(signature, str) and signature not in signatures:
                        signatures.append(signature)
                    attempts_history.append(
                        {
                            "signature": signature,
                            "provider": company_search_metadata.get("provider"),
                            "timestamp": (attempted_at or utcnow()).isoformat(),
                            "result_status": reason_code,
                            "candidate_count": executed_attempt.get("candidates_returned_count", 0),
                            "mode": executed_attempt.get("query_mode"),
                            "params": executed_attempt.get("params_sent"),
                        }
                    )
                metadata["cnpj_paid_search_signatures"] = signatures[-50:]
                metadata["cnpj_paid_search_last_attempts"] = attempts_history[-50:]
                total_paid_calls = metadata.get("cnpj_paid_search_total_paid_calls")
                if not isinstance(total_paid_calls, int):
                    total_paid_calls = 0
                metadata["cnpj_paid_search_total_paid_calls"] = total_paid_calls + len(executed_attempts)
                if company_search_metadata.get("actual_request_made"):
                    last_attempt_at = attempted_at or utcnow()
                    previous_attempt_at = CNPJEnrichmentService._parse_metadata_datetime(
                        metadata.get("cnpj_paid_search_last_attempt_at")
                    )
                    attempts_today = metadata.get("cnpj_paid_search_attempts_today")
                    if not isinstance(attempts_today, int):
                        attempts_today = 0
                    executed_count = max(1, len(executed_attempts))
                    if previous_attempt_at is not None and previous_attempt_at.date() == last_attempt_at.date():
                        attempts_today += executed_count
                    else:
                        attempts_today = executed_count
                    last_signature = executed_attempts[-1].get("query_signature") if executed_attempts else metadata.get("cnpj_paid_search_last_signature")
                    metadata.update(
                        {
                            "cnpj_paid_search_last_signature": last_signature,
                            "cnpj_paid_search_last_attempt_at": last_attempt_at.isoformat(),
                            "cnpj_paid_search_last_result_status": reason_code,
                            "cnpj_paid_search_last_candidates_count": company_search_metadata.get(
                                "candidates_returned_count",
                                0,
                            ),
                            "cnpj_paid_search_last_provider": company_search_metadata.get("provider"),
                            "cnpj_paid_search_attempts_today": attempts_today,
                        }
                    )
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
        paid_calls_made: int,
        paid_calls_skipped_duplicate: int,
        paid_calls_skipped_recent: int,
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
            skipped_review_candidate_count=sum(
                1 for item in results if item.reason_code == REASON_SKIPPED_REVIEW_CANDIDATE_EXISTS
            ),
            paid_search_recently_attempted_count=sum(
                1 for item in results if item.reason_code == REASON_PAID_SEARCH_RECENTLY_ATTEMPTED
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
            company_search_consulted_now_count=sum(
                1 for item in results if item.reason_code in COMPANY_SEARCH_EXECUTED_REASON_CODES
            ),
            paid_calls_made=paid_calls_made,
            paid_calls_skipped_duplicate=paid_calls_skipped_duplicate,
            paid_calls_skipped_recent=paid_calls_skipped_recent,
            provider_rate_limited_count=sum(
                1 for item in results if item.reason_code == REASON_CNPJ_PROVIDER_RATE_LIMITED
            ),
            provider_error_count=sum(1 for item in results if item.reason_code == REASON_PROVIDER_ERROR),
            error_count=sum(1 for item in results if not item.success or item.match_status == "error"),
            errors=errors,
        )
