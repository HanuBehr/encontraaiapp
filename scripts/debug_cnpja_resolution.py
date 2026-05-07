from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.db import session_scope
from app.models.lead import Lead
from app.services.cnpj_enrichment import (
    CLEAR_WINNER_GAP,
    CNPJEnrichmentService,
)
from app.services.providers.cnpja import CNPJAProviderError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Debug the CNPJá CNPJ resolution pipeline for saved leads.")
    parser.add_argument("--lead-ids", required=True, help="Comma-separated lead IDs, e.g. 123,124,125")
    parser.add_argument(
        "--mode",
        choices=("cheap", "balanced", "delivery"),
        default="delivery",
        help="Resolution mode used to build commercial search attempts.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute website extraction, public validation, and paid commercial attempts.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Plan/execute paid attempts even when the lead already has a confirmed CNPJ.",
    )
    return parser.parse_args()


def parse_lead_ids(raw_value: str) -> list[int]:
    lead_ids: list[int] = []
    for chunk in raw_value.split(","):
        stripped = chunk.strip()
        if not stripped:
            continue
        lead_ids.append(int(stripped))
    return lead_ids


def print_heading(title: str) -> None:
    print(f"\n{'=' * 80}\n{title}\n{'=' * 80}")


def print_key_value(label: str, value: Any) -> None:
    if isinstance(value, list):
        rendered = ", ".join(str(item) for item in value) if value else "-"
    else:
        rendered = value if value not in {None, ""} else "-"
    print(f"- {label}: {rendered}")


def summarize_score(candidate_summary: dict[str, Any]) -> None:
    print("Best candidate:")
    print_key_value("CNPJ", candidate_summary.get("cnpj"))
    print_key_value("Razão social", candidate_summary.get("legal_name"))
    print_key_value("Nome fantasia", candidate_summary.get("trade_name"))
    print_key_value("Cidade/UF", join_city_state(candidate_summary.get("city"), candidate_summary.get("state")))
    print_key_value("Endereço", candidate_summary.get("address"))
    print_key_value("Provider", candidate_summary.get("provider"))
    print_key_value("Pontuação", f"{candidate_summary.get('score', '-')} / 100")
    confidence = candidate_summary.get("match_confidence")
    if isinstance(confidence, (int, float)):
        print_key_value("Confiança", f"{round(float(confidence) * 100)}%")
    print_key_value("Motivo revisão", candidate_summary.get("review_reason"))
    print("Score breakdown:")
    for key, value in sorted((candidate_summary.get("evidence") or {}).items()):
        print(f"  + {key}: {value}")
    penalties = candidate_summary.get("penalties") or []
    for penalty in penalties:
        print(f"  - {penalty}")


def join_city_state(city: Any, state: Any) -> str | None:
    city_text = str(city).strip() if isinstance(city, str) else ""
    state_text = str(state).strip() if isinstance(state, str) else ""
    if city_text and state_text:
        return f"{city_text}/{state_text}"
    if city_text:
        return city_text
    if state_text:
        return state_text
    return None


def decide_from_candidate(
    service: CNPJEnrichmentService,
    scored_candidates: list[Any],
) -> tuple[str, dict[str, Any] | None, str | None]:
    if not scored_candidates:
        return "not_found", None, "no_candidates_after_attempts"

    best_candidate = scored_candidates[0]
    top_gap = (
        best_candidate.score - scored_candidates[1].score
        if len(scored_candidates) > 1
        else CLEAR_WINNER_GAP
    )
    blocked_reason = service._blocked_from_autofill_reason(  # noqa: SLF001
        best_candidate,
        top_gap=top_gap,
        require_confirmable_cnpj=True,
    )
    summary = service._build_candidate_summary(  # noqa: SLF001
        best_candidate,
        candidate_count=len(scored_candidates),
        blocked_from_autofill_reason=blocked_reason,
        match_confidence=(
            service._review_confidence(best_candidate.score, blocked_reason)  # noqa: SLF001
            if blocked_reason
            else service._score_to_confidence(best_candidate.score)  # noqa: SLF001
        ),
    )
    if service._is_high_confidence_match(best_candidate, top_gap=top_gap) and blocked_reason is None:  # noqa: SLF001
        return "matched", summary, None
    if service._is_reviewable_company_search_candidate(best_candidate):  # noqa: SLF001
        return "needs_review", summary, blocked_reason or "below_autofill_threshold"
    return "not_found", summary, blocked_reason or "below_review_threshold"


def debug_website_phase(
    service: CNPJEnrichmentService,
    lead: Lead,
    *,
    execute: bool,
) -> tuple[str | None, dict[str, Any] | None]:
    website_url = lead.website or lead.domain
    if not website_url:
        print("Attempt 0 - Website extraction: skipped (lead has no public website).")
        return None, None

    print("Attempt 0 - Website extraction:")
    print_key_value("Website", website_url)
    if not execute:
        print("  Planned: crawl homepage/legal/contact pages, extract CNPJ patterns, validate via public lookup.")
        return None, None

    extraction = service._get_website_extraction(website_url)  # noqa: SLF001
    print_key_value("Candidates extracted", [candidate.cnpj for candidate in extraction.candidates])
    print_key_value("Reason code", extraction.reason_code)
    if not extraction.candidates:
        return None, None

    scored_candidates: list[Any] = []
    for extracted_candidate in extraction.candidates:
        try:
            lookup = service._lookup_known_cnpj_cached(extracted_candidate.cnpj)  # noqa: SLF001
        except Exception as exc:  # noqa: BLE001
            print(f"  Validation failed for {extracted_candidate.cnpj}: {exc}")
            continue
        scored = service._score_website_candidate(lead, lookup, extracted_candidate)  # noqa: SLF001
        scored_candidates.append(scored)
        print(f"  Validated {lookup.cnpj} via {lookup.source_provider} with score {scored.score}")

    scored_candidates.sort(key=lambda item: item.score, reverse=True)
    decision, summary, reason = decide_from_candidate(service, scored_candidates)
    if summary is not None:
        summarize_score(summary)
    print_key_value("Decision after website phase", decision)
    print_key_value("Decision reason", reason)
    return decision, summary


def debug_paid_phase(
    service: CNPJEnrichmentService,
    lead: Lead,
    *,
    mode: str,
    execute: bool,
) -> tuple[str, dict[str, Any] | None, str | None]:
    evidence_profile = service._build_evidence_profile(lead)  # noqa: SLF001
    print("Evidence:")
    for label, value in [
        ("Business name", evidence_profile.business_name),
        ("Category", evidence_profile.category),
        ("City/UF", join_city_state(evidence_profile.city, evidence_profile.state)),
        ("Municipality IBGE", evidence_profile.municipality_ibge_code),
        ("Address", evidence_profile.address_raw),
        ("Street", evidence_profile.street_name),
        ("Number", evidence_profile.address_number),
        ("Neighborhood", evidence_profile.neighborhood),
        ("CEP", evidence_profile.postal_code),
        ("CEP extracted from address", evidence_profile.extracted_zip_from_address),
        ("Phone area (raw)", evidence_profile.raw_phone_area),
        ("Phone area", evidence_profile.phone_area),
        ("Expected phone area", evidence_profile.expected_phone_area),
        ("Phone area conflict", evidence_profile.phone_area_conflict),
        ("Website domain", evidence_profile.website_domain),
        ("Email domain", evidence_profile.email_domain),
        ("Searchable email/domain", evidence_profile.searchable_email_domain),
        ("Searchable domain source", evidence_profile.searchable_email_domain_source),
        ("Alias variants", evidence_profile.alias_variants),
        ("Names variants", evidence_profile.names_variants),
        ("Legal-name variants", evidence_profile.legal_name_variants),
        ("Brand variants", evidence_profile.brand_variants),
        ("Category CNAE group", evidence_profile.category_cnae_group),
    ]:
        print_key_value(label, value)

    if not service._uses_cnpja_commercial_company_search():  # noqa: SLF001
        print("Paid CNPJá commercial search is not enabled for this environment.")
        return "not_found", None, "company_search_not_configured"

    attempts = service._build_cnpja_commercial_attempts(evidence_profile, search_mode=mode)  # noqa: SLF001
    print("Planned attempts:")
    for index, attempt in enumerate(attempts, start=1):
        domain_source = f" [{attempt.domain_source}]" if attempt.domain_source else ""
        print(
            f"  {index}. {attempt.label} ({attempt.mode}) -> "
            f"{attempt.query_param or 'location-only'}{domain_source} | {attempt.params}"
        )

    if not attempts:
        return "not_found", None, "no_attempts_planned"
    if not execute:
        print_key_value("Would spend up to paid calls", min(len(attempts), service._max_paid_calls_for_mode(mode)))  # noqa: SLF001
        return "planned", None, None

    all_candidates: dict[str, Any] = {}
    executed_signatures: set[str] = set()
    paid_calls = 0
    rate_limited = False
    for index, attempt in enumerate(attempts, start=1):
        if paid_calls >= service._max_paid_calls_for_mode(mode):  # noqa: SLF001
            print(f"  Attempt {index} skipped because max paid calls for mode {mode} was reached.")
            break
        if not service._should_execute_attempt_plan(  # noqa: SLF001
            attempt,
            evidence_profile=evidence_profile,
            current_candidates=all_candidates,
        ):
            print(f"  Attempt {index} skipped because an earlier candidate is already reviewable.")
            continue

        signature_payload = service._build_attempt_signature_payload(  # noqa: SLF001
            evidence_profile=evidence_profile,
            provider="cnpja_commercial",
            attempt_plan=attempt,
            search_mode=mode,
        )
        signature = service._build_company_search_signature(signature_payload)  # noqa: SLF001
        if signature in executed_signatures:
            print(f"  Attempt {index} skipped because the exact same params were already executed in this run.")
            continue

        print(f"\nExecuting attempt {index}: {attempt.label}")
        print_key_value("Params", attempt.params)
        executed_signatures.add(signature)
        try:
            matches, attempt_metadata = service.provider.execute_commercial_search_attempt(
                mode=attempt.mode,
                label=attempt.label,
                query_param=attempt.query_param,
                searched_values=attempt.searched_values,
                params=attempt.params,
                reason=attempt.reason,
            )
        except CNPJAProviderError as exc:
            print_key_value("Provider error", str(exc))
            if "usage limit" in str(exc).lower():
                rate_limited = True
            break

        paid_calls += 1
        print_key_value("Provider status", attempt_metadata.get("provider_status"))
        print_key_value("Candidates returned", attempt_metadata.get("candidates_returned_count"))
        for candidate in matches:
            all_candidates.setdefault(candidate.cnpj, candidate)
            print(
                f"  - {candidate.cnpj} | {candidate.trade_name or '-'} | "
                f"{candidate.legal_name or '-'} | {join_city_state(candidate.city, candidate.state) or '-'}"
            )

    if rate_limited:
        return "rate_limited", None, "company_search_rate_limited"

    scored_candidates = sorted(
        (service._score_candidate(evidence_profile, candidate) for candidate in all_candidates.values()),  # noqa: SLF001
        key=lambda item: item.score,
        reverse=True,
    )
    decision, summary, reason = decide_from_candidate(service, scored_candidates)
    return decision, summary, reason


def main() -> int:
    args = parse_args()
    settings = get_settings()
    lead_ids = parse_lead_ids(args.lead_ids)
    if not lead_ids:
        print("No lead IDs were provided.")
        return 1

    if args.execute:
        print("EXECUTE: paid/public provider calls may be made.")
    else:
        print("DRY RUN: no paid API calls will be made.")

    with session_scope() as session:
        service = CNPJEnrichmentService(session, settings)
        leads = session.query(Lead).filter(Lead.id.in_(lead_ids)).order_by(Lead.id.asc()).all()
        found_ids = {lead.id for lead in leads}
        missing_ids = [lead_id for lead_id in lead_ids if lead_id not in found_ids]
        for missing_id in missing_ids:
            print_heading(f"Lead {missing_id} - not found")
        for lead in leads:
            print_heading(f"Lead {lead.id} - {lead.business_name}")
            print_key_value("Current status", lead.cnpj_match_status)
            print_key_value("Current CNPJ", lead.cnpj)
            print_key_value("Current provider", lead.cnpj_source_provider)
            print_key_value("Search mode", args.mode)
            print_key_value("Force paid planning", args.force)

            should_skip_paid, skip_message = service._should_skip_paid_planning(  # noqa: SLF001
                lead,
                force_paid_search=args.force,
            )
            if should_skip_paid:
                print(skip_message)
                continue

            website_decision, website_summary = debug_website_phase(service, lead, execute=args.execute)
            if website_decision == "matched":
                print("Final decision: matched automatically from website-extracted CNPJ.")
                continue
            if website_decision == "needs_review":
                print("Final decision: candidate found via website extraction and needs manual review.")
                continue

            if not args.execute:
                debug_paid_phase(service, lead, mode=args.mode, execute=False)
                continue

            decision, candidate_summary, reason = debug_paid_phase(
                service,
                lead,
                mode=args.mode,
                execute=True,
            )
            if candidate_summary is not None:
                summarize_score(candidate_summary)
            print_key_value("Final decision", decision)
            print_key_value("Decision reason", reason)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
