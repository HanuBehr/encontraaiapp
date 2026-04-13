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
from app.schemas.lead import EnrichmentRunResult
from app.services.normalization import (
    canonicalize_url,
    clean_email,
    extract_emails,
    extract_instagram_links,
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


def extract_public_page_data(html: str, source_url: str) -> PageExtractionResult:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator="\n", strip=True)

    evidences: list[ExtractedEvidence] = []
    seen_keys: set[tuple[str, str]] = set()

    def add_evidence(item: ExtractedEvidence) -> None:
        key = (item.contact_type.value, item.normalized_value or item.raw_value)
        if key in seen_keys:
            return
        seen_keys.add(key)
        evidences.append(item)

    anchor_hrefs: list[str] = []
    text_lines = [line.strip() for line in text.splitlines() if line.strip()]

    for anchor in soup.find_all("a", href=True):
        href = (anchor.get("href") or "").strip()
        anchor_text = anchor.get_text(" ", strip=True)
        lower_href = href.lower()
        if lower_href.startswith("mailto:"):
            email = clean_email(href.split(":", maxsplit=1)[1].split("?", maxsplit=1)[0])
            if email:
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
    )


class EnrichmentService:
    USER_AGENT = "reverse-logistics-mvp/0.1"
    PAGE_PATHS = ("/", "/contato", "/contact", "/sobre", "/about", "/empresa", "/fale-conosco")

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
            for page_url in candidate_urls:
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

                aggregated_signals = self._merge_material_signals(aggregated_signals, extraction.material_signals)

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
            fields_updated=unique_preserve_order(fields_updated),
            last_enriched_at=lead.last_enriched_at or utcnow(),
            material_profile=lead.material_profile or {},
            skipped_reason=skipped_reason,
        )

    def enrich_batch(self, lead_ids: list[int], *, actor: str = "system") -> list[EnrichmentRunResult]:
        results: list[EnrichmentRunResult] = []
        for lead_id in lead_ids:
            results.append(self.enrich_lead(lead_id, actor=actor))
        return results

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
