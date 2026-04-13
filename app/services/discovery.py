from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import Settings
from app.enums import ActivityAction, ContactType, ImportBatchStatus, ImportBatchType
from app.models.activity_log import ActivityLog
from app.models.import_batch import ImportBatch
from app.models.raw_discovery_record import RawDiscoveryRecord
from app.models.base import utcnow
from app.repositories.lead_repository import LeadRepository
from app.schemas.discovery import (
    DiscoveryPreviewItem,
    DiscoveryPreviewResponse,
    DiscoverySearchRequest,
    DiscoverySearchResponse,
    ResolvedLocation,
)
from app.schemas.lead import LeadSummary
from app.services.providers.geocoding import GeocodedLocation, GoogleGeocodingClient
from app.services.providers.google_places import GooglePlacesProvider


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
            items.extend(
                [
                    DiscoveryPreviewItem(
                        search_term=search_term,
                        provider_record_id=result.provider_record_id,
                        source_url=result.source_url,
                        raw_payload=result.raw_payload,
                        candidate=result.candidate,
                    )
                    for result in provider_results
                ]
            )

        return DiscoveryPreviewResponse(
            provider="google_places",
            resolved_location=ResolvedLocation(
                label=resolved.label,
                latitude=resolved.latitude,
                longitude=resolved.longitude,
            ),
            total_provider_results=total_provider_results,
            items=items,
        )

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

    def search(self, request: DiscoverySearchRequest) -> DiscoverySearchResponse:
        preview = self.preview(request)
        return self.ingest_preview(request, preview)

    def _resolve_location(self, request: DiscoverySearchRequest) -> GeocodedLocation:
        if request.latitude is not None and request.longitude is not None:
            label = request.location_query or f"{request.latitude},{request.longitude}"
            return GeocodedLocation(label=label, latitude=request.latitude, longitude=request.longitude)

        assert request.location_query is not None
        return self.geocoder.resolve(request.location_query)
