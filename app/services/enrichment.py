from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.config import Settings
from app.enums import ActivityAction, ContactType
from app.models.activity_log import ActivityLog
from app.models.base import utcnow
from app.models.lead import Lead
from app.models.lead_enrichment_record import LeadEnrichmentRecord
from app.repositories.lead_repository import LeadRepository
from app.schemas.lead import EnrichmentRunResult, LeadBatchEnrichmentResponse, LeadBatchEnrichmentSummary
from app.services.normalization import (
    canonicalize_url,
    clean_email,
    extract_emails,
    extract_instagram_links,
    extract_obfuscated_emails,
    extract_phone_candidates,
    extract_whatsapp_from_url,
    infer_material_signals,
    is_contact_like_url,
    normalize_domain,
    normalize_phone_br,
    unique_preserve_order,
)
from app.services.scoring import ScoringService


@dataclass(slots=True)
class ExtractedEvidence:
    contact_type: ContactType
    raw_value: str
    normalized_value: str | None
    confidence: float
    source_url: str
    label: str | None = None
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "contact_type": self.contact_type.value,
            "raw_value": self.raw_value,
            "normalized_value": self.normalized_value,
            "confidence": self.confidence,
            "source_url": self.source_url,
            "label": self.label,
            "note": self.note,
        }


@dataclass(slots=True)
class PageExtractionResult:
    evidences: list[ExtractedEvidence]
    extracted_fields: dict[str, list[dict[str, Any]]]
    confidence_scores: dict[str, float]
    material_signals: dict[str, dict[str, Any]]
    candidate_page_urls: list[str]


def _decode_cloudflare_email(encoded_value: str | None) -> str | None:
    if not encoded_value:
        return None
    try:
        encoded_bytes = bytes.fromhex(encoded_value)
    except ValueError:
        return None
    if not encoded_bytes:
        return None
    key = encoded_bytes[0]
    decoded = "".join(chr(byte ^ key) for byte in encoded_bytes[1:])
    return clean_email(decoded)


def extract_public_page_data(html: str, source_url: str) -> PageExtractionResult:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator="\n", strip=True)
    source_host = urlparse(source_url).netloc.lower()

    evidences: list[ExtractedEvidence] = []
    seen_keys: set[tuple[str, str]] = set()

    def add_evidence(item: ExtractedEvidence) -> None:
        key = (item.contact_type.value, item.normalized_value or item.raw_value)
        if key in seen_keys:
            return
        seen_keys.add(key)
        evidences.append(item)

    anchor_hrefs: list[str] = []
    candidate_page_urls: list[str] = []
    text_lines = [line.strip() for line in text.splitlines() if line.strip()]

    for anchor in soup.find_all("a", href=True):
        href = (anchor.get("href") or "").strip()
        anchor_text = anchor.get_text(" ", strip=True)
        lower_href = href.lower()
        if lower_href.startswith("mailto:"):
            mailto_payload = href.split(":", maxsplit=1)[1].split("?", maxsplit=1)[0]
            mailto_emails = extract_emails(mailto_payload) or list(extract_obfuscated_emails(mailto_payload))
            for email in mailto_emails:
                add_evidence(
                    ExtractedEvidence(
                        contact_type=ContactType.EMAIL,
                        raw_value=email,
                        normalized_value=email,
                        confidence=0.98,
                        source_url=source_url,
                        label=anchor_text or "mailto",
                    )
                )
            continue
        if lower_href.startswith("tel:"):
            raw_phone = href.split(":", maxsplit=1)[1]
            normalized_phone = normalize_phone_br(raw_phone)
            if normalized_phone:
                confidence = 0.96
                add_evidence(
                    ExtractedEvidence(
                        contact_type=ContactType.PHONE,
                        raw_value=raw_phone,
                        normalized_value=normalized_phone,
                        confidence=confidence,
                        source_url=source_url,
                        label=anchor_text or "tel",
                    )
                )
                if "whatsapp" in anchor_text.lower():
                    add_evidence(
                        ExtractedEvidence(
                            contact_type=ContactType.WHATSAPP,
                            raw_value=raw_phone,
                            normalized_value=normalized_phone,
                            confidence=0.88,
                            source_url=source_url,
                            label=anchor_text or "tel whatsapp",
                        )
                    )
            continue

        canonical_href = canonicalize_url(href, base_url=source_url)
        if not canonical_href:
            continue
        anchor_hrefs.append(canonical_href)

        whatsapp_match = extract_whatsapp_from_url(canonical_href)
        if whatsapp_match:
            raw_value, normalized_value = whatsapp_match
            add_evidence(
                ExtractedEvidence(
                    contact_type=ContactType.WHATSAPP,
                    raw_value=raw_value,
                    normalized_value=normalized_value,
                    confidence=0.99,
                    source_url=source_url,
                    label=anchor_text or "whatsapp_link",
                )
            )

        if is_contact_like_url(canonical_href):
            if urlparse(canonical_href).netloc.lower() == source_host:
                candidate_page_urls.append(canonical_href)
            add_evidence(
                ExtractedEvidence(
                    contact_type=ContactType.CONTACT_FORM,
                    raw_value=canonical_href,
                    normalized_value=canonical_href,
                    confidence=0.55,
                    source_url=source_url,
                    label=anchor_text or "contact_link",
                )
            )

    for tag in soup.find_all(attrs={"data-cfemail": True}):
        email = _decode_cloudflare_email(str(tag.get("data-cfemail") or ""))
        if email:
            add_evidence(
                ExtractedEvidence(
                    contact_type=ContactType.EMAIL,
                    raw_value=email,
                    normalized_value=email,
                    confidence=0.9,
                    source_url=source_url,
                    label="cloudflare_email",
                )
            )

    for email in extract_emails(text):
        add_evidence(
            ExtractedEvidence(
                contact_type=ContactType.EMAIL,
                raw_value=email,
                normalized_value=email,
                confidence=0.92,
                source_url=source_url,
            )
        )

    for email in extract_emails(html):
        add_evidence(
            ExtractedEvidence(
                contact_type=ContactType.EMAIL,
                raw_value=email,
                normalized_value=email,
                confidence=0.88,
                source_url=source_url,
                label="html_source",
            )
        )

    for email in extract_obfuscated_emails("\n".join([text, html])):
        add_evidence(
            ExtractedEvidence(
                contact_type=ContactType.EMAIL,
                raw_value=email,
                normalized_value=email,
                confidence=0.82,
                source_url=source_url,
                label="obfuscated_email",
            )
        )

    for raw_phone, normalized_phone in extract_phone_candidates(text):
        add_evidence(
            ExtractedEvidence(
                contact_type=ContactType.PHONE,
                raw_value=raw_phone,
                normalized_value=normalized_phone,
                confidence=0.78,
                source_url=source_url,
            )
        )

    for line in text_lines:
        if "whatsapp" not in line.lower():
            continue
        for raw_phone, normalized_phone in extract_phone_candidates(line):
            add_evidence(
                ExtractedEvidence(
                    contact_type=ContactType.WHATSAPP,
                    raw_value=raw_phone,
                    normalized_value=normalized_phone,
                    confidence=0.86,
                    source_url=source_url,
                    label="whatsapp_text",
                )
            )

    for instagram_url in extract_instagram_links(anchor_hrefs):
        add_evidence(
            ExtractedEvidence(
                contact_type=ContactType.INSTAGRAM,
                raw_value=instagram_url,
                normalized_value=instagram_url,
                confidence=0.93,
                source_url=source_url,
            )
        )

    for form in soup.find_all("form"):
        action_url = canonicalize_url(form.get("action") or source_url, base_url=source_url)
        if not action_url:
            continue
        add_evidence(
            ExtractedEvidence(
                contact_type=ContactType.CONTACT_FORM,
                raw_value=action_url,
                normalized_value=action_url,
                confidence=0.84,
                source_url=source_url,
                label="html_form",
            )
        )

    context_text = " ".join([text, *anchor_hrefs])
    material_signals = infer_material_signals(context_text)

    extracted_fields: dict[str, list[dict[str, Any]]] = {
        "emails": [item.to_dict() for item in evidences if item.contact_type == ContactType.EMAIL],
        "phones": [item.to_dict() for item in evidences if item.contact_type == ContactType.PHONE],
        "whatsapps": [item.to_dict() for item in evidences if item.contact_type == ContactType.WHATSAPP],
        "instagram_links": [item.to_dict() for item in evidences if item.contact_type == ContactType.INSTAGRAM],
        "contact_form_urls": [item.to_dict() for item in evidences if item.contact_type == ContactType.CONTACT_FORM],
    }
    confidence_scores = {
        field_name: max((item["confidence"] for item in items), default=0.0)
        for field_name, items in extracted_fields.items()
    }
    confidence_scores["material_signals"] = max(
        (float(details.get("confidence", 0.0)) for details in material_signals.values()),
        default=0.0,
    )

    return PageExtractionResult(
        evidences=evidences,
        extracted_fields=extracted_fields,
        confidence_scores=confidence_scores,
        material_signals=material_signals,
        candidate_page_urls=unique_preserve_order(candidate_page_urls),
    )


class EnrichmentService:
    USER_AGENT = "reverse-logistics-mvp/0.1"
    PAGE_PATHS = (
        "/",
        "/contato",
        "/contact",
        "/atendimento",
        "/sac",
        "/fale-conosco",
        "/faleconosco",
        "/sobre",
        "/about",
        "/empresa",
        "/institucional",
        "/quem-somos",
    )
    MAX_DISCOVERED_CONTACT_PAGES = 4

    def __init__(
        self,
        db: Session,
        settings: Settings,
        http_session: requests.Session | None = None,
    ) -> None:
        self.db = db
        self.settings = settings
        self.repository = LeadRepository(db)
        self.http = http_session or requests.Session()
        self.robot_cache: dict[str, RobotFileParser | None] = {}

    def enrich_lead(self, lead_id: int, *, actor: str = "system") -> EnrichmentRunResult:
        lead = self.repository.get_by_id(lead_id)
        if lead is None:
            raise ValueError(f"Lead {lead_id} not found.")

        pages_attempted = 0
        pages_fetched = 0
        contacts_added = 0
        contacts_added_by_type: dict[str, int] = {}
        aggregated_signals: dict[str, dict[str, Any]] = {}
        skipped_reason: str | None = None

        website_url = canonicalize_url(lead.website)
        if website_url and lead.website != website_url:
            lead.website = website_url
            lead.domain = normalize_domain(website_url)

        candidate_urls = self._build_candidate_urls(lead)
        if not candidate_urls:
            skipped_reason = "Lead has no public website."
            self._create_enrichment_record(
                lead=lead,
                source_url=lead.source_url or "no_public_website",
                page_type="missing_website",
                http_status=None,
                robots_allowed=True,
                extracted_fields={},
                confidence_scores={},
                material_signals={},
                note=skipped_reason,
            )
        else:
            seen_candidate_urls = set(candidate_urls)
            discovered_contact_pages = 0
            page_index = 0
            while page_index < len(candidate_urls):
                page_url = candidate_urls[page_index]
                page_index += 1
                pages_attempted += 1
                page_type = self._classify_page(page_url, website_url or page_url)
                robots_allowed = self._can_fetch(page_url)
                if not robots_allowed:
                    self._create_enrichment_record(
                        lead=lead,
                        source_url=page_url,
                        page_type=page_type,
                        http_status=None,
                        robots_allowed=False,
                        extracted_fields={},
                        confidence_scores={},
                        material_signals={},
                        note="Blocked by robots.txt",
                    )
                    continue

                try:
                    response = self.http.get(
                        page_url,
                        headers={"User-Agent": self.USER_AGENT},
                        timeout=20,
                        allow_redirects=True,
                    )
                except requests.RequestException as exc:
                    self._create_enrichment_record(
                        lead=lead,
                        source_url=page_url,
                        page_type=page_type,
                        http_status=None,
                        robots_allowed=True,
                        extracted_fields={},
                        confidence_scores={},
                        material_signals={},
                        note=f"Request failed: {exc}",
                    )
                    continue

                content_type = (response.headers.get("content-type") or "").lower()
                if response.status_code >= 400 or "html" not in content_type:
                    self._create_enrichment_record(
                        lead=lead,
                        source_url=response.url,
                        page_type=page_type,
                        http_status=response.status_code,
                        robots_allowed=True,
                        extracted_fields={},
                        confidence_scores={},
                        material_signals={},
                        note=f"Skipped content type: {content_type or 'unknown'}",
                    )
                    continue

                pages_fetched += 1
                extraction = extract_public_page_data(response.text, response.url)
                record = self._create_enrichment_record(
                    lead=lead,
                    source_url=response.url,
                    page_type=page_type,
                    http_status=response.status_code,
                    robots_allowed=True,
                    extracted_fields=extraction.extracted_fields,
                    confidence_scores=extraction.confidence_scores,
                    material_signals=extraction.material_signals,
                    note=None,
                )

                for evidence in extraction.evidences:
                    contact = self.repository.add_contact_if_missing(
                        lead_id=lead.id,
                        contact_type=evidence.contact_type,
                        raw_value=evidence.raw_value,
                        normalized_value=evidence.normalized_value,
                        source_url=evidence.source_url,
                        source_kind="public_website",
                        source_record_type="lead_enrichment_record",
                        source_record_id=record.id,
                        confidence=evidence.confidence,
                        label=evidence.label,
                        note=evidence.note,
                    )
                    if contact is not None:
                        contacts_added += 1
                        contact_type_key = evidence.contact_type.value
                        contacts_added_by_type[contact_type_key] = contacts_added_by_type.get(contact_type_key, 0) + 1

                aggregated_signals = self._merge_material_signals(aggregated_signals, extraction.material_signals)
                for discovered_url in extraction.candidate_page_urls:
                    if discovered_contact_pages >= self.MAX_DISCOVERED_CONTACT_PAGES:
                        break
                    if discovered_url in seen_candidate_urls:
                        continue
                    if not self._is_same_host(discovered_url, website_url or page_url):
                        continue
                    candidate_urls.append(discovered_url)
                    seen_candidate_urls.add(discovered_url)
                    discovered_contact_pages += 1

        fields_updated = self.repository.sync_canonical_contacts(lead)
        if lead.website and not lead.domain:
            lead.domain = normalize_domain(lead.website)
            if lead.domain:
                fields_updated.append("domain")
        if aggregated_signals:
            merged_material_profile = self._merge_material_signals(lead.material_profile or {}, aggregated_signals)
            if merged_material_profile != (lead.material_profile or {}):
                lead.material_profile = merged_material_profile
                fields_updated.append("material_profile")

        lead.last_enriched_at = utcnow()
        if "last_enriched_at" not in fields_updated:
            fields_updated.append("last_enriched_at")

        scoring_result = ScoringService(self.db).score_lead_instance(lead)

        self.db.add(
            ActivityLog(
                organization_id=lead.organization_id or self.repository.organization_id,
                lead_id=lead.id,
                entity_type="lead",
                entity_id=lead.id,
                action=ActivityAction.ENRICHED,
                actor=actor,
                message="Public website enrichment completed.",
                metadata_json={
                    "pages_attempted": pages_attempted,
                    "pages_fetched": pages_fetched,
                    "contacts_added": contacts_added,
                    "fields_updated": fields_updated,
                    "lead_score": scoring_result.lead_score,
                    "skipped_reason": skipped_reason,
                },
            )
        )
        self.db.commit()
        self.db.refresh(lead)

        return EnrichmentRunResult(
            lead_id=lead.id,
            business_name=lead.business_name,
            pages_attempted=pages_attempted,
            pages_fetched=pages_fetched,
            contacts_added=contacts_added,
            contacts_added_by_type=contacts_added_by_type,
            fields_updated=unique_preserve_order(fields_updated),
            last_enriched_at=lead.last_enriched_at or utcnow(),
            material_profile=lead.material_profile or {},
            skipped_reason=skipped_reason,
        )

    def enrich_batch(self, lead_ids: list[int], *, actor: str = "system") -> list[EnrichmentRunResult]:
        return self.enrich_lead_ids(
            lead_ids,
            actor=actor,
            scope_label="lead ids",
            continue_on_error=False,
        ).results

    def enrich_lead_ids(
        self,
        lead_ids: list[int],
        *,
        actor: str = "system",
        scope_label: str = "lead ids",
        continue_on_error: bool = True,
    ) -> LeadBatchEnrichmentResponse:
        requested_ids = [int(lead_id) for lead_id in dict.fromkeys(lead_ids)]
        results: list[EnrichmentRunResult] = []
        error_messages: list[str] = []

        for lead_id in requested_ids:
            try:
                results.append(self.enrich_lead(lead_id, actor=actor))
            except ValueError as exc:
                self.db.rollback()
                if not continue_on_error:
                    raise
                error_messages.append(f"Lead {lead_id}: {exc}")

        summary = self._build_batch_summary(
            requested_ids=requested_ids,
            results=results,
            error_messages=error_messages,
            scope_label=scope_label,
        )
        return LeadBatchEnrichmentResponse(processed=len(results), results=results, summary=summary)

    def enrich_latest_import_batch(
        self,
        *,
        actor: str = "system",
        continue_on_error: bool = True,
    ) -> LeadBatchEnrichmentResponse:
        batch = self.repository.get_latest_completed_import_batch()
        if batch is None:
            summary = LeadBatchEnrichmentSummary(
                scope_label="latest import batch",
                error_messages=["No completed import batch with leads is available."],
                errors=1,
            )
            return LeadBatchEnrichmentResponse(processed=0, results=[], summary=summary)

        lead_ids = self.repository.list_lead_ids_for_import_batch(batch.id)
        return self.enrich_lead_ids(
            lead_ids,
            actor=actor,
            scope_label=f"latest import batch {batch.id}",
            continue_on_error=continue_on_error,
        )

    def enrich_saved_queue(
        self,
        lead_ids: list[int],
        *,
        actor: str = "system",
        queue_label: str = "current saved working queue",
        continue_on_error: bool = True,
    ) -> LeadBatchEnrichmentResponse:
        return self.enrich_lead_ids(
            lead_ids,
            actor=actor,
            scope_label=queue_label,
            continue_on_error=continue_on_error,
        )

    @staticmethod
    def _build_batch_summary(
        *,
        requested_ids: list[int],
        results: list[EnrichmentRunResult],
        error_messages: list[str],
        scope_label: str,
    ) -> LeadBatchEnrichmentSummary:
        def added(contact_type: ContactType) -> int:
            return sum(result.contacts_added_by_type.get(contact_type.value, 0) for result in results)

        return LeadBatchEnrichmentSummary(
            scope_label=scope_label,
            requested=len(requested_ids),
            processed=len(results),
            contacts_added=sum(result.contacts_added for result in results),
            emails_found=added(ContactType.EMAIL),
            instagrams_found=added(ContactType.INSTAGRAM),
            whatsapps_found=added(ContactType.WHATSAPP),
            contact_forms_found=added(ContactType.CONTACT_FORM),
            skipped=sum(1 for result in results if result.skipped_reason),
            skipped_no_website=sum(1 for result in results if result.skipped_reason == "Lead has no public website."),
            errors=len(error_messages),
            error_messages=error_messages,
            pages_attempted=sum(result.pages_attempted for result in results),
            pages_fetched=sum(result.pages_fetched for result in results),
        )

    def _build_candidate_urls(self, lead: Lead) -> list[str]:
        website_url = canonicalize_url(lead.website)
        if not website_url:
            return []

        parsed = urlparse(website_url)
        root_url = f"{parsed.scheme}://{parsed.netloc}/"
        urls = [website_url, root_url]
        urls.extend(urljoin(root_url, path) for path in self.PAGE_PATHS)
        same_host_urls = [
            candidate
            for candidate in unique_preserve_order(urls)
            if urlparse(candidate).netloc.lower() == parsed.netloc.lower()
        ]
        return same_host_urls

    @staticmethod
    def _is_same_host(candidate_url: str, base_url: str) -> bool:
        return urlparse(candidate_url).netloc.lower() == urlparse(base_url).netloc.lower()

    def _get_robot_parser(self, target_url: str) -> RobotFileParser | None:
        parsed = urlparse(target_url)
        root_key = f"{parsed.scheme}://{parsed.netloc}"
        if root_key in self.robot_cache:
            return self.robot_cache[root_key]

        robots_url = urljoin(f"{root_key}/", "robots.txt")
        try:
            response = self.http.get(robots_url, headers={"User-Agent": self.USER_AGENT}, timeout=10)
            if response.status_code >= 400 or not response.text.strip():
                self.robot_cache[root_key] = None
                return None
            parser = RobotFileParser()
            parser.parse(response.text.splitlines())
            self.robot_cache[root_key] = parser
            return parser
        except requests.RequestException:
            self.robot_cache[root_key] = None
            return None

    def _can_fetch(self, target_url: str) -> bool:
        parser = self._get_robot_parser(target_url)
        if parser is None:
            return True
        return parser.can_fetch(self.USER_AGENT, target_url)

    def _create_enrichment_record(
        self,
        *,
        lead: Lead,
        source_url: str,
        page_type: str,
        http_status: int | None,
        robots_allowed: bool,
        extracted_fields: dict[str, Any],
        confidence_scores: dict[str, Any],
        material_signals: dict[str, Any],
        note: str | None,
    ) -> LeadEnrichmentRecord:
        record = LeadEnrichmentRecord(
            organization_id=lead.organization_id or self.repository.organization_id,
            lead_id=lead.id,
            source_url=source_url,
            page_type=page_type,
            http_status=http_status,
            robots_allowed=robots_allowed,
            extracted_fields=extracted_fields,
            confidence_scores=confidence_scores,
            inferred_material_signals=material_signals,
            note=note,
        )
        self.db.add(record)
        self.db.flush()
        return record

    @staticmethod
    def _classify_page(page_url: str, base_url: str) -> str:
        normalized_path = urlparse(page_url).path.rstrip("/") or "/"
        if page_url.rstrip("/") == base_url.rstrip("/"):
            return "homepage"
        if "contato" in normalized_path or "contact" in normalized_path or "fale" in normalized_path:
            return "contact"
        if "sobre" in normalized_path or "about" in normalized_path or "empresa" in normalized_path:
            return "about"
        return "website_page"

    @staticmethod
    def _merge_material_signals(
        current: dict[str, Any],
        incoming: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {
            key: {
                "relevant": bool(value.get("relevant", False)),
                "confidence": float(value.get("confidence", 0.0)),
                "matched_keywords": list(value.get("matched_keywords", [])),
            }
            for key, value in current.items()
        }

        for signal_name, payload in incoming.items():
            current_payload = merged.setdefault(
                signal_name,
                {"relevant": False, "confidence": 0.0, "matched_keywords": []},
            )
            current_payload["relevant"] = bool(current_payload["relevant"] or payload.get("relevant", False))
            current_payload["confidence"] = round(
                max(float(current_payload.get("confidence", 0.0)), float(payload.get("confidence", 0.0))),
                2,
            )
            combined_keywords = list(current_payload.get("matched_keywords", [])) + list(
                payload.get("matched_keywords", [])
            )
            current_payload["matched_keywords"] = unique_preserve_order(combined_keywords)

        return merged
