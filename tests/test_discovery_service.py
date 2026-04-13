from __future__ import annotations

from sqlalchemy import func, select

from app.config import Settings
from app.models.activity_log import ActivityLog
from app.models.import_batch import ImportBatch
from app.models.lead import Lead
from app.models.raw_discovery_record import RawDiscoveryRecord
from app.schemas.discovery import DiscoveryLeadCandidate, DiscoverySearchRequest
from app.services.discovery import DiscoveryService
from app.services.providers.discovery_base import ProviderLeadResult
from app.services.providers.geocoding import GeocodedLocation
from app.services.normalization import normalize_business_name


def _candidate(name: str, *, category: str, phone: str, city: str) -> DiscoveryLeadCandidate:
    return DiscoveryLeadCandidate(
        business_name=name,
        normalized_business_name=normalize_business_name(name) or name.lower(),
        category=category,
        city=city,
        state="SP",
        phone=phone,
        whatsapp=phone,
        source_provider="google_places",
        source_url=f"https://maps.google.com/?q={name}",
        google_maps_url=f"https://maps.google.com/?q={name}",
        google_place_id=f"place-{name.lower().replace(' ', '-')}",
        lead_source_type="google_places",
    )


def test_discovery_preview_and_ingest(db_session, monkeypatch) -> None:
    settings = Settings(APP_ENV="test", DATABASE_URL="sqlite://", GOOGLE_API_KEY="test-key")
    service = DiscoveryService(db_session, settings)
    request = DiscoverySearchRequest(
        search_terms=["oficina mecânica", "auto elétrica"],
        location_query="Campinas, SP",
        radius_m=2500,
        max_results_per_term=5,
    )

    monkeypatch.setattr(
        service,
        "_resolve_location",
        lambda payload: GeocodedLocation(label="Campinas - SP, Brasil", latitude=-22.9056, longitude=-47.0608),
    )

    provider_results = {
        "oficina mecânica": [
            ProviderLeadResult(
                candidate=_candidate(
                    "Oficina Torque",
                    category="oficina mecânica",
                    phone="+5511999991111",
                    city="Campinas",
                ),
                raw_payload={"id": "place-oficina-torque"},
                provider_record_id="place-oficina-torque",
                source_url="https://maps.google.com/?q=Oficina+Torque",
            )
        ],
        "auto elétrica": [
            ProviderLeadResult(
                candidate=_candidate(
                    "Auto Elétrica Raio",
                    category="auto elétrica",
                    phone="+5511999992222",
                    city="Campinas",
                ),
                raw_payload={"id": "place-auto-eletrica-raio"},
                provider_record_id="place-auto-eletrica-raio",
                source_url="https://maps.google.com/?q=Auto+Eletrica+Raio",
            )
        ],
    }

    monkeypatch.setattr(
        service.provider,
        "search",
        lambda *, search_term, location_label, latitude, longitude, radius_m, max_results: provider_results[
            search_term
        ],
    )

    preview = service.preview(request)

    assert preview.provider == "google_places"
    assert preview.total_provider_results == 2
    assert len(preview.items) == 2
    assert db_session.scalar(select(func.count(Lead.id))) == 0
    assert db_session.scalar(select(func.count(ImportBatch.id))) == 0

    response = service.ingest_preview(request, preview)

    assert response.total_provider_results == 2
    assert response.created_leads == 2
    assert response.updated_leads == 0
    assert len(response.leads) == 2
    assert db_session.scalar(select(func.count(Lead.id))) == 2
    assert db_session.scalar(select(func.count(ImportBatch.id))) == 1
    assert db_session.scalar(select(func.count(RawDiscoveryRecord.id))) == 2
    assert db_session.scalar(select(func.count(ActivityLog.id))) == 2
