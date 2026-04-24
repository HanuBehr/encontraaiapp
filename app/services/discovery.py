from __future__ import annotations

from hashlib import sha1
import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings
from app.enums import ActivityAction, ContactType, ImportBatchStatus, ImportBatchType
from app.models.activity_log import ActivityLog
from app.models.import_batch import ImportBatch
from app.models.raw_discovery_record import RawDiscoveryRecord
from app.models.base import utcnow
from app.repositories.lead_repository import LeadRepository
from app.schemas.discovery import (
    DiscoveryLeadCandidate,
    DiscoveryExclusionMetadata,
    DiscoveryImportBatchSummary,
    DiscoveryImportResponse,
    DiscoveryImportSkippedItem,
    DiscoveryPreviewEnrichmentMetadata,
    DiscoveryPreviewEnrichmentResponse,
    DiscoveryPreviewEnrichmentSummary,
    DiscoveryPreviewItem,
    DiscoveryPreviewResponse,
    DiscoveryPreviewWebsiteRecoveryResponse,
    DiscoveryPreviewWebsiteRecoverySummary,
    DiscoverySearchRequest,
    DiscoverySearchResponse,
    ResolvedLocation,
)
from app.schemas.lead import LeadSummary
from app.services.enrichment import EnrichmentService
from app.services.exclusion_rules import ExclusionRuleService
from app.services.normalization import canonicalize_url, is_non_business_website_domain, normalize_domain
from app.services.providers.geocoding import GeocodedLocation, GoogleGeocodingClient
from app.services.providers.google_places import GooglePlacesProvider

logger = logging.getLogger(__name__)

_RAW_WEBSITE_PATHS = (
    ("websiteUri",),
    ("website",),
    ("websiteUrl",),
    ("website_url",),
    ("businessProfile", "websiteUri"),
    ("businessProfile", "website"),
    ("metadata", "websiteUri"),
    ("metadata", "website"),
)
class DiscoveryService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.lead_repository = LeadRepository(db)
        self.geocoder = GoogleGeocodingClient(settings)
        self.provider = GooglePlacesProvider(settings)

    def preview(self, request: DiscoverySearchRequest) -> DiscoveryPreviewResponse:
        resolved = self._resolve_location(request)
        items: list[DiscoveryPreviewItem] = []
        total_provider_results = 0

        for search_term in request.search_terms:
            provider_results = self.provider.search(
                search_term=search_term,
                location_label=resolved.label,
                latitude=resolved.latitude,
                longitude=resolved.longitude,
                radius_m=request.radius_m,
                max_results=request.max_results_per_term,
            )
            total_provider_results += len(provider_results)
            base_index = len(items)
            for result_index, result in enumerate(provider_results):
                candidate = self._recover_preview_candidate_contact_fields(
                    result.candidate,
                    raw_payload=result.raw_payload,
                    source_url=result.source_url,
                )
                items.append(
                    DiscoveryPreviewItem(
                        client_result_id=_client_result_id(
                            search_term=search_term,
                            provider_record_id=result.provider_record_id,
                            google_place_id=candidate.google_place_id,
                            normalized_business_name=candidate.normalized_business_name,
                            city=candidate.city,
                            source_url=result.source_url,
                            index=base_index + result_index,
                        ),
                        search_term=search_term,
                        provider_record_id=result.provider_record_id,
                        source_url=result.source_url,
                        raw_payload=result.raw_payload,
                        candidate=candidate,
                    )
                )

        preview = DiscoveryPreviewResponse(
            provider="google_places",
            resolved_location=ResolvedLocation(
                label=resolved.label,
                latitude=resolved.latitude,
                longitude=resolved.longitude,
            ),
            total_provider_results=total_provider_results,
            items=items,
        )
        return self.evaluate_preview_exclusions(preview)

    def evaluate_preview_exclusions(self, preview: DiscoveryPreviewResponse) -> DiscoveryPreviewResponse:
        exclusion_service = ExclusionRuleService(self.db, organization_id=self.lead_repository.organization_id)
        annotated_items: list[DiscoveryPreviewItem] = []
        for index, item in enumerate(preview.items):
            recovered_candidate = self._recover_preview_candidate_contact_fields(
                item.candidate,
                raw_payload=item.raw_payload,
                source_url=item.source_url,
            )
            client_result_id = self._preview_item_client_result_id(item, index)
            try:
                match = exclusion_service.evaluate_candidate(recovered_candidate)
            except SQLAlchemyError:
                raise
            except Exception:
                logger.exception(
                    "Discovery exclusion evaluation failed for preview item.",
                    extra={
                        "client_result_id": client_result_id,
                        "business_name": item.candidate.business_name,
                    },
                )
                match = None
            annotated_items.append(
                item.model_copy(
                    update={
                        "candidate": recovered_candidate,
                        "client_result_id": client_result_id,
                        "exclusion": _exclusion_metadata(match),
                    }
                )
            )

        return preview.model_copy(update={"items": annotated_items})

    def _preview_item_client_result_id(self, item: DiscoveryPreviewItem, index: int) -> str:
        if item.client_result_id:
            return item.client_result_id
        try:
            return _client_result_id(
                search_term=item.search_term,
                provider_record_id=item.provider_record_id,
                google_place_id=item.candidate.google_place_id,
                normalized_business_name=item.candidate.normalized_business_name,
                city=item.candidate.city,
                source_url=item.source_url,
                index=index,
            )
        except Exception:
            fallback_client_result_id = f"preview-item-{index}"
            logger.exception(
                "Discovery preview client_result_id generation failed; using fallback id.",
                extra={
                    "fallback_client_result_id": fallback_client_result_id,
                    "business_name": item.candidate.business_name,
                },
            )
            return fallback_client_result_id

    def _recover_preview_candidate_contact_fields(
        self,
        candidate: DiscoveryLeadCandidate,
        *,
        raw_payload: dict[str, object],
        source_url: str | None,
    ) -> DiscoveryLeadCandidate:
        recovered_website = (
            self._canonical_business_website(candidate.website)
            or self._canonical_business_website(candidate.domain)
            or self._recover_business_website_from_payload(raw_payload)
            or self._canonical_business_website(source_url)
        )
        recovered_domain = normalize_domain(candidate.domain) or normalize_domain(recovered_website)
        if (
            recovered_website == candidate.website
            and recovered_domain == candidate.domain
        ):
            return candidate
        return candidate.model_copy(
            update={
                "website": recovered_website,
                "domain": recovered_domain,
            }
        )

    def _recover_business_website_from_payload(self, raw_payload: dict[str, object]) -> str | None:
        for path in _RAW_WEBSITE_PATHS:
            candidate_value = _nested_payload_value(raw_payload, path)
            website = self._canonical_business_website(candidate_value if isinstance(candidate_value, str) else None)
            if website:
                return website
        return None

    def _canonical_business_website(self, value: str | None) -> str | None:
        canonical = canonicalize_url(value)
        if not canonical:
            return None
        domain = normalize_domain(canonical)
        if not domain or is_non_business_website_domain(domain):
            return None
        return canonical

    def _preview_item_with_enrichment_outcome(
        self,
        item: DiscoveryPreviewItem,
        *,
        candidate=None,
        enrichment=None,
    ) -> DiscoveryPreviewItem:
        payload = item.model_dump(mode="json")
        if candidate is not None:
            payload["candidate"] = candidate.model_dump(mode="json")
        if enrichment is not None:
            payload["enrichment"] = enrichment.model_dump(mode="json")
        return DiscoveryPreviewItem.model_validate(payload)

    def _failed_preview_enrichment_item(
        self,
        item: DiscoveryPreviewItem,
        error_message: str,
    ) -> DiscoveryPreviewItem:
        return self._preview_item_with_enrichment_outcome(
            item,
            enrichment=DiscoveryPreviewEnrichmentMetadata(
                success=False,
                error_message=error_message,
            ),
        )

    def enrich_preview(
        self,
        *,
        preview: DiscoveryPreviewResponse,
        client_result_ids: list[str],
        skip_blocked: bool = True,
    ) -> DiscoveryPreviewEnrichmentResponse:
        try:
            return self._enrich_preview_once(
                preview=preview,
                client_result_ids=client_result_ids,
                skip_blocked=skip_blocked,
            )
        except SQLAlchemyError:
            raise
        except Exception:
            self.db.rollback()
            logger.exception(
                "Discovery preview enrichment failed request-wide; retrying selected rows in isolation.",
                extra={
                    "requested_client_result_ids": client_result_ids,
                    "requested_count": len(client_result_ids),
                },
            )
            return self._retry_enrich_preview_in_isolation(
                preview=preview,
                client_result_ids=client_result_ids,
                skip_blocked=skip_blocked,
            )

    def _enrich_preview_once(
        self,
        *,
        preview: DiscoveryPreviewResponse,
        client_result_ids: list[str],
        skip_blocked: bool = True,
    ) -> DiscoveryPreviewEnrichmentResponse:
        annotated_preview = self.evaluate_preview_exclusions(preview)
        indexed_items = {item.client_result_id: item for item in annotated_preview.items if item.client_result_id}
        requested_ids = list(dict.fromkeys(client_result_ids))
        missing_ids = [client_id for client_id in requested_ids if client_id not in indexed_items]
        if missing_ids:
            raise ValueError(f"Selected preview item(s) were not found: {', '.join(missing_ids)}")

        previous_blocked = {
            item.client_result_id: item.exclusion.is_blocked
            for item in annotated_preview.items
            if item.client_result_id
        }
        requested_id_set = set(requested_ids)
        enrichment_service = EnrichmentService(self.db, self.settings)
        updated_items: list[DiscoveryPreviewItem] = []
        processed = 0
        success_count = 0
        emails_found = 0
        instagrams_found = 0
        contact_forms_found = 0
        no_email_found = 0
        skipped_no_website = 0
        errors = 0
        error_messages: list[str] = []

        for item in annotated_preview.items:
            client_result_id = item.client_result_id
            if not client_result_id or client_result_id not in requested_id_set:
                updated_items.append(item)
                continue

            if skip_blocked and item.exclusion.is_blocked:
                updated_items.append(
                    self._preview_item_with_enrichment_outcome(
                        item,
                        enrichment=DiscoveryPreviewEnrichmentMetadata(
                            success=True,
                            skipped_reason="Skipped blocked preview row.",
                        ),
                    )
                )
                continue

            processed += 1
            try:
                candidate, enrichment = enrichment_service.enrich_preview_candidate(item.candidate)
                validated_item = self._preview_item_with_enrichment_outcome(
                    item,
                    candidate=candidate,
                    enrichment=enrichment,
                )
                validated_enrichment = validated_item.enrichment or DiscoveryPreviewEnrichmentMetadata()
            except Exception as exc:
                self.db.rollback()
                errors += 1
                error_message = EnrichmentService._short_error_message(exc)
                error_messages.append(f"{item.candidate.business_name}: {error_message}")
                logger.exception(
                    "Discovery preview enrichment failed for preview item.",
                    extra={
                        "client_result_id": client_result_id,
                        "business_name": item.candidate.business_name,
                    },
                )
                updated_items.append(self._failed_preview_enrichment_item(item, error_message))
                continue

            success_count += 1
            emails_found += int(validated_enrichment.email_found)
            instagrams_found += int(validated_enrichment.instagram_found)
            contact_forms_found += int(validated_enrichment.contact_form_found)
            no_email_found += int(validated_enrichment.no_email_found)
            skipped_no_website += int(validated_enrichment.skipped_reason == "No public website.")
            updated_items.append(validated_item)

        reevaluated_preview = self.evaluate_preview_exclusions(
            annotated_preview.model_copy(update={"items": updated_items})
        )
        blocked_after_enrichment = sum(
            1
            for item in reevaluated_preview.items
            if item.client_result_id in requested_id_set
            and not previous_blocked.get(item.client_result_id, False)
            and item.exclusion.is_blocked
        )

        return DiscoveryPreviewEnrichmentResponse(
            preview=reevaluated_preview,
            summary=DiscoveryPreviewEnrichmentSummary(
                requested=len(requested_ids),
                processed=processed,
                success_count=success_count,
                emails_found=emails_found,
                instagrams_found=instagrams_found,
                contact_forms_found=contact_forms_found,
                no_email_found=no_email_found,
                skipped_no_website=skipped_no_website,
                blocked_after_enrichment=blocked_after_enrichment,
                errors=errors,
                error_messages=error_messages,
            ),
        )

    def _retry_enrich_preview_in_isolation(
        self,
        *,
        preview: DiscoveryPreviewResponse,
        client_result_ids: list[str],
        skip_blocked: bool,
    ) -> DiscoveryPreviewEnrichmentResponse:
        requested_ids = list(dict.fromkeys(client_result_ids))
        current_preview = preview
        processed = 0
        success_count = 0
        emails_found = 0
        instagrams_found = 0
        contact_forms_found = 0
        no_email_found = 0
        skipped_no_website = 0
        blocked_after_enrichment = 0
        errors = 0
        error_messages: list[str] = []

        for client_result_id in requested_ids:
            try:
                single_response = self._enrich_preview_once(
                    preview=current_preview,
                    client_result_ids=[client_result_id],
                    skip_blocked=skip_blocked,
                )
            except SQLAlchemyError:
                raise
            except Exception as exc:
                self.db.rollback()
                processed += 1
                errors += 1
                business_name = self._preview_business_name(current_preview, client_result_id)
                error_message = EnrichmentService._short_error_message(exc)
                error_messages.append(f"{business_name}: {error_message}")
                logger.exception(
                    "Discovery preview enrichment failed for isolated retry row.",
                    extra={
                        "client_result_id": client_result_id,
                        "business_name": business_name,
                    },
                )
                current_preview = self._preview_with_failed_row(
                    current_preview,
                    client_result_id=client_result_id,
                    error_message=error_message,
                )
                continue

            current_preview = single_response.preview
            summary = single_response.summary
            processed += summary.processed
            success_count += summary.success_count
            emails_found += summary.emails_found
            instagrams_found += summary.instagrams_found
            contact_forms_found += summary.contact_forms_found
            no_email_found += summary.no_email_found
            skipped_no_website += summary.skipped_no_website
            blocked_after_enrichment += summary.blocked_after_enrichment
            errors += summary.errors
            error_messages.extend(summary.error_messages)

        return DiscoveryPreviewEnrichmentResponse(
            preview=current_preview,
            summary=DiscoveryPreviewEnrichmentSummary(
                requested=len(requested_ids),
                processed=processed,
                success_count=success_count,
                emails_found=emails_found,
                instagrams_found=instagrams_found,
                contact_forms_found=contact_forms_found,
                no_email_found=no_email_found,
                skipped_no_website=skipped_no_website,
                blocked_after_enrichment=blocked_after_enrichment,
                errors=errors,
                error_messages=error_messages,
            ),
        )

    def _preview_business_name(self, preview: DiscoveryPreviewResponse, client_result_id: str) -> str:
        for item in preview.items:
            if item.client_result_id == client_result_id:
                return item.candidate.business_name
        return client_result_id

    def _preview_with_failed_row(
        self,
        preview: DiscoveryPreviewResponse,
        *,
        client_result_id: str,
        error_message: str,
    ) -> DiscoveryPreviewResponse:
        updated_items = [
            self._failed_preview_enrichment_item(item, error_message)
            if item.client_result_id == client_result_id
            else item
            for item in preview.items
        ]
        return preview.model_copy(update={"items": updated_items})

    def recover_preview_websites(
        self,
        *,
        preview: DiscoveryPreviewResponse,
        client_result_ids: list[str],
        skip_blocked: bool = True,
    ) -> DiscoveryPreviewWebsiteRecoveryResponse:
        annotated_preview = self.evaluate_preview_exclusions(preview)
        indexed_items = {item.client_result_id: item for item in annotated_preview.items if item.client_result_id}
        requested_ids = list(dict.fromkeys(client_result_ids))
        missing_ids = [client_id for client_id in requested_ids if client_id not in indexed_items]
        if missing_ids:
            raise ValueError(f"Selected preview item(s) were not found: {', '.join(missing_ids)}")

        previous_blocked = {
            item.client_result_id: item.exclusion.is_blocked
            for item in annotated_preview.items
            if item.client_result_id
        }
        requested_id_set = set(requested_ids)
        updated_items: list[DiscoveryPreviewItem] = []
        processed = 0
        recovered_count = 0
        no_website_found = 0
        skipped_existing_website = 0
        skipped_missing_place_id = 0
        skipped_blocked = 0
        errors = 0
        error_messages: list[str] = []

        for item in annotated_preview.items:
            client_result_id = item.client_result_id
            if not client_result_id or client_result_id not in requested_id_set:
                updated_items.append(item)
                continue

            if skip_blocked and item.exclusion.is_blocked:
                skipped_blocked += 1
                updated_items.append(item)
                continue

            if has_usable_website(item.candidate):
                skipped_existing_website += 1
                updated_items.append(item)
                continue

            place_id = self._preview_item_place_id(item)
            if not place_id:
                skipped_missing_place_id += 1
                updated_items.append(item)
                continue

            processed += 1
            try:
                details_payload = self.provider.fetch_place_details(place_id)
                recovered_candidate = self._recover_preview_candidate_contact_fields(
                    item.candidate,
                    raw_payload=details_payload,
                    source_url=(details_payload.get("googleMapsUri") if isinstance(details_payload.get("googleMapsUri"), str) else None)
                    or item.source_url,
                )
            except Exception as exc:
                self.db.rollback()
                errors += 1
                error_message = EnrichmentService._short_error_message(exc)
                error_messages.append(f"{item.candidate.business_name}: {error_message}")
                logger.exception(
                    "Discovery website recovery failed for preview item.",
                    extra={
                        "client_result_id": client_result_id,
                        "business_name": item.candidate.business_name,
                        "place_id": place_id,
                    },
                )
                updated_items.append(item)
                continue

            if has_usable_website(recovered_candidate):
                recovered_count += 1
                updated_items.append(
                    item.model_copy(
                        update={
                            "candidate": recovered_candidate,
                            "raw_payload": _merge_payload_dicts(item.raw_payload, details_payload),
                            "source_url": recovered_candidate.google_maps_url or item.source_url,
                        }
                    )
                )
            else:
                no_website_found += 1
                updated_items.append(item)

        reevaluated_preview = self.evaluate_preview_exclusions(
            annotated_preview.model_copy(update={"items": updated_items})
        )
        blocked_after_recovery = sum(
            1
            for item in reevaluated_preview.items
            if item.client_result_id in requested_id_set
            and not previous_blocked.get(item.client_result_id, False)
            and item.exclusion.is_blocked
        )

        return DiscoveryPreviewWebsiteRecoveryResponse(
            preview=reevaluated_preview,
            summary=DiscoveryPreviewWebsiteRecoverySummary(
                requested=len(requested_ids),
                processed=processed,
                recovered_count=recovered_count,
                no_website_found=no_website_found,
                skipped_existing_website=skipped_existing_website,
                skipped_missing_place_id=skipped_missing_place_id,
                skipped_blocked=skipped_blocked,
                blocked_after_recovery=blocked_after_recovery,
                errors=errors,
                error_messages=error_messages,
            ),
        )

    def _preview_item_place_id(self, item: DiscoveryPreviewItem) -> str | None:
        candidate_place_id = (item.candidate.google_place_id or "").strip()
        if candidate_place_id:
            return candidate_place_id
        provider_record_id = (item.provider_record_id or "").strip()
        if provider_record_id:
            return provider_record_id
        raw_place_id = item.raw_payload.get("id")
        if isinstance(raw_place_id, str) and raw_place_id.strip():
            return raw_place_id.strip()
        return None

    def ingest_preview(
        self,
        request: DiscoverySearchRequest,
        preview: DiscoveryPreviewResponse,
    ) -> DiscoverySearchResponse:
        batch = ImportBatch(
            batch_type=ImportBatchType.DISCOVERY,
            status=ImportBatchStatus.RUNNING,
            source_provider=preview.provider,
            source_query=" | ".join(request.search_terms),
            location_label=preview.resolved_location.label,
            input_payload=request.model_dump(mode="json"),
            started_at=utcnow(),
        )
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)

        created_ids: set[int] = set()
        updated_ids: set[int] = set()
        response_leads: dict[int, LeadSummary] = {}

        try:
            for item in preview.items:
                lead, created = self.lead_repository.upsert_from_discovery(item.candidate)
                self.db.flush()

                raw_record = RawDiscoveryRecord(
                    import_batch_id=batch.id,
                    lead_id=lead.id,
                    provider=preview.provider,
                    provider_record_id=item.provider_record_id,
                    search_term=item.search_term,
                    search_input=request.location_query or f"{request.latitude},{request.longitude}",
                    center_lat=preview.resolved_location.latitude,
                    center_lng=preview.resolved_location.longitude,
                    radius_m=request.radius_m,
                    source_url=item.source_url,
                    payload_json=item.raw_payload,
                )
                self.db.add(raw_record)
                self.db.flush()

                if item.candidate.phone:
                    self.lead_repository.add_contact_if_missing(
                        lead_id=lead.id,
                        contact_type=ContactType.PHONE,
                        raw_value=item.candidate.phone,
                        normalized_value=item.candidate.phone,
                        source_url=item.source_url,
                        source_kind="provider",
                        source_record_type="raw_discovery_record",
                        source_record_id=raw_record.id,
                        confidence=0.9,
                        is_primary=(lead.phone == item.candidate.phone),
                    )
                    self.lead_repository.add_contact_if_missing(
                        lead_id=lead.id,
                        contact_type=ContactType.WHATSAPP,
                        raw_value=item.candidate.phone,
                        normalized_value=item.candidate.whatsapp,
                        source_url=item.source_url,
                        source_kind="provider",
                        source_record_type="raw_discovery_record",
                        source_record_id=raw_record.id,
                        confidence=0.5,
                        is_primary=(lead.whatsapp == item.candidate.whatsapp),
                    )

                self.db.add(
                    ActivityLog(
                        organization_id=lead.organization_id or self.lead_repository.organization_id,
                        lead_id=lead.id,
                        entity_type="lead",
                        entity_id=lead.id,
                        action=ActivityAction.DISCOVERED,
                        metadata_json={
                            "search_term": item.search_term,
                            "provider": preview.provider,
                            "import_batch_id": batch.id,
                            "provider_record_id": item.provider_record_id,
                        },
                    )
                )

                if created:
                    created_ids.add(lead.id)
                else:
                    updated_ids.add(lead.id)

                response_leads[lead.id] = LeadSummary.model_validate(lead)

            batch.record_count = preview.total_provider_results
            batch.status = ImportBatchStatus.COMPLETED
            batch.completed_at = utcnow()
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            failed_batch = self.db.get(ImportBatch, batch.id)
            if failed_batch is not None:
                failed_batch.status = ImportBatchStatus.FAILED
                failed_batch.notes = str(exc)
                failed_batch.completed_at = utcnow()
                self.db.commit()
            raise

        updated_ids -= created_ids
        return DiscoverySearchResponse(
            batch_id=batch.id,
            provider="google_places",
            resolved_location=ResolvedLocation(
                label=preview.resolved_location.label,
                latitude=preview.resolved_location.latitude,
                longitude=preview.resolved_location.longitude,
            ),
            total_provider_results=preview.total_provider_results,
            created_leads=len(created_ids),
            updated_leads=len(updated_ids),
            leads=list(response_leads.values()),
        )

    def import_preview(
        self,
        *,
        request: DiscoverySearchRequest,
        preview: DiscoveryPreviewResponse,
        selected_client_result_ids: list[str],
        skip_blocked: bool = True,
    ) -> DiscoveryImportResponse:
        annotated_preview = self.evaluate_preview_exclusions(preview)
        indexed_items = {item.client_result_id: item for item in annotated_preview.items if item.client_result_id}
        missing_ids = [client_id for client_id in selected_client_result_ids if client_id not in indexed_items]
        if missing_ids:
            raise ValueError(f"Selected preview item(s) were not found: {', '.join(missing_ids)}")

        selected_items = [indexed_items[client_id] for client_id in dict.fromkeys(selected_client_result_ids)]
        skipped_items: list[DiscoveryImportSkippedItem] = []
        import_items: list[DiscoveryPreviewItem] = []
        for item in selected_items:
            if skip_blocked and item.exclusion.is_blocked:
                skipped_items.append(
                    DiscoveryImportSkippedItem(
                        client_result_id=item.client_result_id or "",
                        business_name=item.candidate.business_name,
                        reason=item.exclusion.reason or "Matched an active exclusion rule.",
                        exclusion=item.exclusion,
                    )
                )
                continue
            import_items.append(item)

        batch = ImportBatch(
            batch_type=ImportBatchType.DISCOVERY,
            status=ImportBatchStatus.RUNNING,
            source_provider=annotated_preview.provider,
            source_query=" | ".join(request.search_terms),
            location_label=annotated_preview.resolved_location.label,
            input_payload={
                **request.model_dump(mode="json"),
                "selected_client_result_ids": selected_client_result_ids,
                "skip_blocked": skip_blocked,
            },
            started_at=utcnow(),
        )
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)

        created_ids: set[int] = set()
        updated_ids: set[int] = set()
        saved_lead_ids: list[int] = []
        response_leads: dict[int, LeadSummary] = {}

        try:
            for item in import_items:
                lead, created = self.lead_repository.upsert_from_discovery(item.candidate)
                self.db.flush()

                raw_record = RawDiscoveryRecord(
                    import_batch_id=batch.id,
                    lead_id=lead.id,
                    provider=annotated_preview.provider,
                    provider_record_id=item.provider_record_id,
                    search_term=item.search_term,
                    search_input=request.location_query or f"{request.latitude},{request.longitude}",
                    center_lat=annotated_preview.resolved_location.latitude,
                    center_lng=annotated_preview.resolved_location.longitude,
                    radius_m=request.radius_m,
                    source_url=item.source_url,
                    payload_json=item.raw_payload,
                )
                self.db.add(raw_record)
                self.db.flush()

                if item.candidate.phone:
                    self.lead_repository.add_contact_if_missing(
                        lead_id=lead.id,
                        contact_type=ContactType.PHONE,
                        raw_value=item.candidate.phone,
                        normalized_value=item.candidate.phone,
                        source_url=item.source_url,
                        source_kind="provider",
                        source_record_type="raw_discovery_record",
                        source_record_id=raw_record.id,
                        confidence=0.9,
                        is_primary=(lead.phone == item.candidate.phone),
                    )
                    self.lead_repository.add_contact_if_missing(
                        lead_id=lead.id,
                        contact_type=ContactType.WHATSAPP,
                        raw_value=item.candidate.phone,
                        normalized_value=item.candidate.whatsapp,
                        source_url=item.source_url,
                        source_kind="provider",
                        source_record_type="raw_discovery_record",
                        source_record_id=raw_record.id,
                        confidence=0.5,
                        is_primary=(lead.whatsapp == item.candidate.whatsapp),
                    )

                self.db.add(
                    ActivityLog(
                        organization_id=lead.organization_id or self.lead_repository.organization_id,
                        lead_id=lead.id,
                        entity_type="lead",
                        entity_id=lead.id,
                        action=ActivityAction.DISCOVERED,
                        metadata_json={
                            "search_term": item.search_term,
                            "provider": annotated_preview.provider,
                            "import_batch_id": batch.id,
                            "provider_record_id": item.provider_record_id,
                            "client_result_id": item.client_result_id,
                        },
                    )
                )

                if created:
                    created_ids.add(lead.id)
                else:
                    updated_ids.add(lead.id)

                saved_lead_ids.append(lead.id)
                response_leads[lead.id] = LeadSummary.model_validate(lead)

            batch.record_count = len(import_items)
            batch.status = ImportBatchStatus.COMPLETED
            batch.completed_at = utcnow()
            self.db.commit()
            self.db.refresh(batch)
        except Exception as exc:
            self.db.rollback()
            failed_batch = self.db.get(ImportBatch, batch.id)
            if failed_batch is not None:
                failed_batch.status = ImportBatchStatus.FAILED
                failed_batch.notes = str(exc)
                failed_batch.completed_at = utcnow()
                self.db.commit()
            raise

        updated_ids -= created_ids
        unique_saved_lead_ids = list(dict.fromkeys(saved_lead_ids))
        return DiscoveryImportResponse(
            batch=DiscoveryImportBatchSummary(
                id=batch.id,
                status=batch.status,
                source_provider=batch.source_provider,
                source_query=batch.source_query,
                location_label=batch.location_label,
                record_count=batch.record_count,
                lead_count=len(unique_saved_lead_ids),
                started_at=batch.started_at,
                completed_at=batch.completed_at,
                created_at=batch.created_at,
                updated_at=batch.updated_at,
            ),
            batch_id=batch.id,
            provider=annotated_preview.provider,
            resolved_location=annotated_preview.resolved_location,
            total_preview_items=len(annotated_preview.items),
            selected_items=len(selected_items),
            saved_items=len(import_items),
            skipped_blocked=len(skipped_items),
            created_leads=len(created_ids),
            updated_leads=len(updated_ids),
            saved_lead_ids=unique_saved_lead_ids,
            leads=list(response_leads.values()),
            skipped_items=skipped_items,
        )

    def search(self, request: DiscoverySearchRequest) -> DiscoverySearchResponse:
        preview = self.preview(request)
        return self.ingest_preview(request, preview)

    def _resolve_location(self, request: DiscoverySearchRequest) -> GeocodedLocation:
        if request.latitude is not None and request.longitude is not None:
            label = request.location_query or f"{request.latitude},{request.longitude}"
            return GeocodedLocation(label=label, latitude=request.latitude, longitude=request.longitude)

        assert request.location_query is not None
        return self.geocoder.resolve(request.location_query)


def _exclusion_metadata(match) -> DiscoveryExclusionMetadata:
    if match is None:
        return DiscoveryExclusionMetadata()
    return DiscoveryExclusionMetadata(
        is_blocked=True,
        rule_id=match.rule_id,
        rule_type=match.rule_type,
        pattern=match.pattern,
        reason=match.reason,
    )


def _nested_payload_value(payload: object, path: tuple[str, ...]) -> object | None:
    current = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current
def _merge_payload_dicts(
    current_payload: dict[str, object],
    incoming_payload: dict[str, object],
) -> dict[str, object]:
    return {
        **current_payload,
        **incoming_payload,
    }


def has_usable_website(candidate: DiscoveryLeadCandidate) -> bool:
    return bool(candidate.website or candidate.domain)


def _client_result_id(
    *,
    search_term: str,
    provider_record_id: str | None,
    google_place_id: str | None,
    normalized_business_name: str | None,
    city: str | None,
    source_url: str | None,
    index: int,
) -> str:
    seed = "|".join(
        [
            search_term or "",
            provider_record_id or "",
            google_place_id or "",
            normalized_business_name or "",
            city or "",
            source_url or "",
            str(index),
        ]
    )
    return sha1(seed.encode("utf-8")).hexdigest()
