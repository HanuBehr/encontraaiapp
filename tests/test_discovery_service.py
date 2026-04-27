from __future__ import annotations

import requests
from sqlalchemy import func, select

from app.config import Settings
from app.models.activity_log import ActivityLog
from app.models.import_batch import ImportBatch
from app.models.lead import Lead
from app.models.raw_discovery_record import RawDiscoveryRecord
from app.schemas.discovery import (
    DiscoveryLeadCandidate,
    DiscoveryPreviewEnrichmentMetadata,
    DiscoveryPreviewItem,
    DiscoveryPreviewResponse,
    DiscoverySearchRequest,
    ResolvedLocation,
)
from app.services.discovery import DiscoveryService
from app.services.exclusion_rules import ExclusionRuleService
from app.services.providers.discovery_base import ProviderLeadResult
from app.services.providers.geocoding import GeocodedLocation
from app.services.providers.google_places import GooglePlacesProvider, GooglePlacesProviderError
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


class _FakeGooglePlacesResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_discovery_preview_and_ingest(db_session, monkeypatch) -> None:
    settings = Settings(APP_ENV="test", DATABASE_URL="sqlite://", GOOGLE_API_KEY="test-key")
    service = DiscoveryService(db_session, settings)
    request = DiscoverySearchRequest(
        raw_query="oficinas mecânicas em Campinas",
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
    batch = db_session.scalar(select(ImportBatch))
    assert batch is not None
    assert batch.source_query == "oficinas mecânicas em Campinas"
    assert db_session.scalar(select(func.count(Lead.id))) == 2
    assert db_session.scalar(select(func.count(ImportBatch.id))) == 1
    assert db_session.scalar(select(func.count(RawDiscoveryRecord.id))) == 2
    assert db_session.scalar(select(func.count(ActivityLog.id))) == 2


def test_google_places_provider_retries_transient_ssl_error_and_succeeds(monkeypatch) -> None:
    provider = GooglePlacesProvider(Settings(APP_ENV="test", DATABASE_URL="sqlite://", GOOGLE_API_KEY="test-key"))
    attempts = {"count": 0}

    def fake_post(*args, **kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise requests.exceptions.SSLError("UNEXPECTED_EOF_WHILE_READING")
        return _FakeGooglePlacesResponse({"places": []})

    monkeypatch.setattr("app.services.providers.google_places.requests.request", fake_post)
    monkeypatch.setattr("app.services.providers.google_places.time.sleep", lambda *_: None)

    results = provider.search(
        search_term="loja de tintas",
        location_label="Campinas, SP",
        latitude=-22.9056,
        longitude=-47.0608,
        radius_m=2500,
        max_results=5,
    )

    assert results == []
    assert attempts["count"] == 2


def test_google_places_provider_uses_page_size_for_requested_results(monkeypatch) -> None:
    provider = GooglePlacesProvider(Settings(APP_ENV="test", DATABASE_URL="sqlite://", GOOGLE_API_KEY="test-key"))
    request_bodies: list[dict] = []

    def fake_request(method, url, **kwargs):
        request_bodies.append(kwargs["json"])
        return _FakeGooglePlacesResponse({"places": []})

    monkeypatch.setattr("app.services.providers.google_places.requests.request", fake_request)

    results = provider.search(
        search_term="industria calcadista",
        location_label="Zona Oeste, Sao Paulo",
        latitude=-23.5505,
        longitude=-46.6333,
        radius_m=10000,
        max_results=20,
    )

    assert results == []
    assert len(request_bodies) == 1
    assert request_bodies[0]["pageSize"] == 20
    assert "maxResultCount" not in request_bodies[0]


def test_google_places_provider_paginates_up_to_requested_max(monkeypatch) -> None:
    provider = GooglePlacesProvider(Settings(APP_ENV="test", DATABASE_URL="sqlite://", GOOGLE_API_KEY="test-key"))
    request_bodies: list[dict] = []

    def _place(index: int) -> dict:
        return {
            "id": f"place-{index}",
            "displayName": {"text": f"Empresa {index}"},
            "location": {"latitude": -23.5505, "longitude": -46.6333},
            "googleMapsUri": f"https://maps.google.com/?q=Empresa+{index}",
        }

    responses = [
        _FakeGooglePlacesResponse(
            {
                "places": [_place(index) for index in range(1, 21)],
                "nextPageToken": "page-2-token",
            }
        ),
        _FakeGooglePlacesResponse(
            {
                "places": [_place(index) for index in range(21, 31)],
            }
        ),
    ]

    def fake_request(method, url, **kwargs):
        request_bodies.append(kwargs["json"])
        return responses[len(request_bodies) - 1]

    monkeypatch.setattr("app.services.providers.google_places.requests.request", fake_request)

    results = provider.search(
        search_term="industria calcadista",
        location_label="Zona Oeste, Sao Paulo",
        latitude=-23.5505,
        longitude=-46.6333,
        radius_m=10000,
        max_results=25,
    )

    assert len(results) == 25
    assert len(request_bodies) == 2
    assert request_bodies[0]["pageSize"] == 20
    assert "pageToken" not in request_bodies[0]
    assert request_bodies[1]["pageSize"] == 5
    assert request_bodies[1]["pageToken"] == "page-2-token"


def test_google_places_provider_requires_google_api_key_for_location_discovery() -> None:
    provider = GooglePlacesProvider(Settings(APP_ENV="test", DATABASE_URL="sqlite://", GOOGLE_API_KEY=""))

    try:
        provider.search(
            search_term="dentistas",
            location_label="Sao Paulo, SP",
            latitude=-23.5505,
            longitude=-46.6333,
            radius_m=2500,
            max_results=5,
        )
    except GooglePlacesProviderError as exc:
        assert str(exc) == "GOOGLE_API_KEY must be configured to use location-based discovery."
        assert exc.status_code == 503
    else:
        raise AssertionError("Expected GooglePlacesProviderError to be raised.")


def test_google_places_provider_raises_clean_error_after_transient_request_failures(monkeypatch) -> None:
    provider = GooglePlacesProvider(Settings(APP_ENV="test", DATABASE_URL="sqlite://", GOOGLE_API_KEY="test-key"))

    def fake_post(*args, **kwargs):
        raise requests.exceptions.Timeout("upstream timeout")

    monkeypatch.setattr("app.services.providers.google_places.requests.request", fake_post)
    monkeypatch.setattr("app.services.providers.google_places.time.sleep", lambda *_: None)

    try:
        provider.search(
            search_term="loja de tintas",
            location_label="Campinas, SP",
            latitude=-22.9056,
            longitude=-47.0608,
            radius_m=2500,
            max_results=5,
        )
    except GooglePlacesProviderError as exc:
        assert str(exc) == "Google Places request failed due to an upstream SSL/network error. Retry shortly."
        assert exc.status_code == 503
    else:
        raise AssertionError("Expected GooglePlacesProviderError to be raised.")


def test_google_places_provider_maps_address_to_street_plus_number_and_state_uf() -> None:
    provider = GooglePlacesProvider(Settings(APP_ENV="test", DATABASE_URL="sqlite://", GOOGLE_API_KEY="test-key"))

    result = provider._to_result(
        {
            "id": "place-casa-paulista",
            "displayName": {"text": "Casa Paulista"},
            "formattedAddress": "Avenida Paulista, 1578 - Bela Vista, Sao Paulo - Sao Paulo, 01310-200, Brasil",
            "addressComponents": [
                {"longText": "1578", "shortText": "1578", "types": ["street_number"]},
                {"longText": "Avenida Paulista", "shortText": "Av. Paulista", "types": ["route"]},
                {"longText": "Bela Vista", "shortText": "Bela Vista", "types": ["sublocality_level_1", "sublocality"]},
                {"longText": "Sao Paulo", "shortText": "Sao Paulo", "types": ["locality"]},
                {"longText": "Sao Paulo", "shortText": "SP", "types": ["administrative_area_level_1"]},
                {"longText": "01310-200", "shortText": "01310-200", "types": ["postal_code"]},
            ],
            "location": {"latitude": -23.5614, "longitude": -46.6565},
            "websiteUri": "https://casapaulista.com.br",
            "googleMapsUri": "https://maps.google.com/?q=Casa+Paulista",
            "nationalPhoneNumber": "(11) 3333-4444",
            "primaryTypeDisplayName": {"text": "Materiais de construcao"},
        }
    )

    assert result.candidate.address == "Avenida Paulista, 1578"
    assert result.candidate.neighborhood == "Bela Vista"
    assert result.candidate.city == "Sao Paulo"
    assert result.candidate.state == "SP"
    assert result.candidate.postal_code == "01310-200"


def test_discovery_recover_preview_websites_fetches_place_details_and_rechecks_exclusions(db_session, monkeypatch) -> None:
    settings = Settings(APP_ENV="test", DATABASE_URL="sqlite://", GOOGLE_API_KEY="test-key")
    service = DiscoveryService(db_session, settings)
    ExclusionRuleService(db_session, organization_id=service.lead_repository.organization_id).create_rule(
        rule_type="domain",
        pattern="blocked.com",
        reason="Blocked after website recovery",
    )

    preview = DiscoveryPreviewResponse(
        provider="google_places",
        resolved_location=ResolvedLocation(
            label="Campinas, SP",
            latitude=-22.9056,
            longitude=-47.0608,
        ),
        total_provider_results=1,
        items=[
            DiscoveryPreviewItem(
                client_result_id="recover-1",
                search_term="loja de tintas",
                provider_record_id="place-recover-1",
                source_url="https://maps.google.com/?q=Recuperada",
                raw_payload={},
                candidate=_candidate(
                    "Recuperada",
                    category="loja de tintas",
                    phone="+5511999991111",
                    city="Campinas",
                ).model_copy(update={"website": None, "domain": None, "google_place_id": "place-recover-1"}),
            )
        ],
    )

    monkeypatch.setattr(
        service.provider,
        "fetch_place_details",
        lambda place_id: {
            "id": place_id,
            "websiteUri": "blocked.com",
            "googleMapsUri": "https://maps.google.com/?q=Recuperada",
        },
    )

    response = service.recover_preview_websites(
        preview=preview,
        client_result_ids=["recover-1"],
    )

    assert response.summary.requested == 1
    assert response.summary.processed == 1
    assert response.summary.recovered_count == 1
    assert response.summary.blocked_after_recovery == 1
    assert response.summary.errors == 0
    assert response.preview.items[0].candidate.website == "https://blocked.com"
    assert response.preview.items[0].candidate.domain == "blocked.com"
    assert response.preview.items[0].exclusion.is_blocked is True
    assert response.preview.items[0].exclusion.rule_type == "domain"


def test_discovery_recover_preview_websites_keeps_request_alive_when_one_row_fails(db_session, monkeypatch) -> None:
    settings = Settings(APP_ENV="test", DATABASE_URL="sqlite://", GOOGLE_API_KEY="test-key")
    service = DiscoveryService(db_session, settings)
    preview = DiscoveryPreviewResponse(
        provider="google_places",
        resolved_location=ResolvedLocation(
            label="Campinas, SP",
            latitude=-22.9056,
            longitude=-47.0608,
        ),
        total_provider_results=2,
        items=[
            DiscoveryPreviewItem(
                client_result_id="recover-good-1",
                search_term="loja de tintas",
                provider_record_id="place-recover-good-1",
                source_url="https://maps.google.com/?q=Boa+Recuperada",
                raw_payload={},
                candidate=_candidate(
                    "Boa Recuperada",
                    category="loja de tintas",
                    phone="+5511999991111",
                    city="Campinas",
                ).model_copy(update={"website": None, "domain": None, "google_place_id": "place-recover-good-1"}),
            ),
            DiscoveryPreviewItem(
                client_result_id="recover-bad-1",
                search_term="loja de tintas",
                provider_record_id="place-recover-bad-1",
                source_url="https://maps.google.com/?q=Ruim+Recuperada",
                raw_payload={},
                candidate=_candidate(
                    "Ruim Recuperada",
                    category="loja de tintas",
                    phone="+5511999992222",
                    city="Campinas",
                ).model_copy(update={"website": None, "domain": None, "google_place_id": "place-recover-bad-1"}),
            ),
        ],
    )

    def fake_fetch_place_details(place_id: str) -> dict[str, str]:
        if place_id == "place-recover-bad-1":
            raise RuntimeError("detail lookup failed")
        return {
            "id": place_id,
            "websiteUri": "https://boa-recuperada.example.com",
        }

    monkeypatch.setattr(service.provider, "fetch_place_details", fake_fetch_place_details)

    response = service.recover_preview_websites(
        preview=preview,
        client_result_ids=["recover-good-1", "recover-bad-1"],
    )

    assert response.summary.requested == 2
    assert response.summary.processed == 2
    assert response.summary.recovered_count == 1
    assert response.summary.errors == 1
    assert response.summary.error_messages == ["Ruim Recuperada: detail lookup failed"]
    by_id = {item.client_result_id: item for item in response.preview.items}
    assert by_id["recover-good-1"].candidate.website == "https://boa-recuperada.example.com"
    assert by_id["recover-good-1"].candidate.domain == "boa-recuperada.example.com"
    assert by_id["recover-bad-1"].candidate.website is None
    assert by_id["recover-bad-1"].candidate.domain is None


def test_discovery_preview_recovers_website_from_provider_raw_payload(db_session, monkeypatch) -> None:
    settings = Settings(APP_ENV="test", DATABASE_URL="sqlite://", GOOGLE_API_KEY="test-key")
    service = DiscoveryService(db_session, settings)
    request = DiscoverySearchRequest(
        search_terms=["loja de tintas"],
        location_query="Campinas, SP",
        radius_m=2500,
        max_results_per_term=5,
    )

    monkeypatch.setattr(
        service,
        "_resolve_location",
        lambda payload: GeocodedLocation(label="Campinas - SP, Brasil", latitude=-22.9056, longitude=-47.0608),
    )

    def fake_provider_search(**kwargs):
        candidate = _candidate(
            "Tintas Recuperadas",
            category="loja de tintas",
            phone="+5511999991111",
            city="Campinas",
        ).model_copy(update={"website": None, "domain": None})
        return [
            ProviderLeadResult(
                candidate=candidate,
                raw_payload={
                    "websiteUrl": "www.tintasrecuperadas.com.br",
                    "googleMapsUri": "https://maps.google.com/?q=Tintas+Recuperadas",
                },
                provider_record_id="place-tintas-recuperadas",
                source_url="https://maps.google.com/?q=Tintas+Recuperadas",
            )
        ]

    monkeypatch.setattr(service.provider, "search", fake_provider_search)

    preview = service.preview(request)

    assert len(preview.items) == 1
    assert preview.items[0].candidate.website == "https://www.tintasrecuperadas.com.br"
    assert preview.items[0].candidate.domain == "tintasrecuperadas.com.br"


def test_discovery_preview_passes_requested_max_results_to_provider(db_session, monkeypatch) -> None:
    settings = Settings(APP_ENV="test", DATABASE_URL="sqlite://", GOOGLE_API_KEY="test-key")
    service = DiscoveryService(db_session, settings)
    request = DiscoverySearchRequest(
        raw_query="industria calcadista",
        search_terms=["industria calcadista"],
        location_query="Zona Oeste, Sao Paulo",
        radius_m=10000,
        max_results_per_term=20,
    )

    monkeypatch.setattr(
        service,
        "_resolve_location",
        lambda payload: GeocodedLocation(label="Zona Oeste, Sao Paulo", latitude=-23.5505, longitude=-46.6333),
    )

    provider_calls: list[dict[str, object]] = []

    def fake_provider_search(**kwargs):
        provider_calls.append(kwargs)
        return []

    monkeypatch.setattr(service.provider, "search", fake_provider_search)

    preview = service.preview(request)

    assert preview.total_provider_results == 0
    assert len(provider_calls) == 1
    assert provider_calls[0]["search_term"] == "industria calcadista"
    assert provider_calls[0]["max_results"] == 20


def test_discovery_preview_recovers_website_from_candidate_domain(db_session, monkeypatch) -> None:
    settings = Settings(APP_ENV="test", DATABASE_URL="sqlite://", GOOGLE_API_KEY="test-key")
    service = DiscoveryService(db_session, settings)
    request = DiscoverySearchRequest(
        search_terms=["loja de tintas"],
        location_query="Campinas, SP",
        radius_m=2500,
        max_results_per_term=5,
    )

    monkeypatch.setattr(
        service,
        "_resolve_location",
        lambda payload: GeocodedLocation(label="Campinas - SP, Brasil", latitude=-22.9056, longitude=-47.0608),
    )

    def fake_provider_search(**kwargs):
        candidate = _candidate(
            "Tintas Dominio",
            category="loja de tintas",
            phone="+5511999991111",
            city="Campinas",
        ).model_copy(update={"website": None, "domain": "lojatintasdominio.com.br"})
        return [
            ProviderLeadResult(
                candidate=candidate,
                raw_payload={},
                provider_record_id="place-tintas-dominio",
                source_url="https://maps.google.com/?q=Tintas+Dominio",
            )
        ]

    monkeypatch.setattr(service.provider, "search", fake_provider_search)

    preview = service.preview(request)

    assert len(preview.items) == 1
    assert preview.items[0].candidate.website == "https://lojatintasdominio.com.br"
    assert preview.items[0].candidate.domain == "lojatintasdominio.com.br"


def test_discovery_preview_re_evaluates_and_import_skips_blocked_items(db_session, monkeypatch) -> None:
    settings = Settings(APP_ENV="test", DATABASE_URL="sqlite://", GOOGLE_API_KEY="test-key")
    service = DiscoveryService(db_session, settings)
    request = DiscoverySearchRequest(
        search_terms=["loja de tintas"],
        location_query="Campinas, SP",
        radius_m=2500,
        max_results_per_term=5,
    )

    monkeypatch.setattr(
        service,
        "_resolve_location",
        lambda payload: GeocodedLocation(label="Campinas - SP, Brasil", latitude=-22.9056, longitude=-47.0608),
    )

    provider_calls: list[str] = []

    def fake_provider_search(**kwargs):
        provider_calls.append(kwargs["search_term"])
        return [
            ProviderLeadResult(
                candidate=_candidate(
                    "Casa das Tintas",
                    category="loja de tintas",
                    phone="+5511999991111",
                    city="Campinas",
                ),
                raw_payload={"id": "place-casa-das-tintas"},
                provider_record_id="place-casa-das-tintas",
                source_url="https://maps.google.com/?q=Casa+das+Tintas",
            ),
            ProviderLeadResult(
                candidate=_candidate(
                    "Mega Chain Campinas",
                    category="loja de tintas",
                    phone="+5511999992222",
                    city="Campinas",
                ),
                raw_payload={"id": "place-mega-chain-campinas"},
                provider_record_id="place-mega-chain-campinas",
                source_url="https://maps.google.com/?q=Mega+Chain+Campinas",
            ),
        ]

    monkeypatch.setattr(service.provider, "search", fake_provider_search)

    preview = service.preview(request)

    assert provider_calls == ["loja de tintas"]
    assert len(preview.items) == 2
    assert all(item.client_result_id for item in preview.items)
    assert all(not item.exclusion.is_blocked for item in preview.items)

    ExclusionRuleService(db_session, organization_id=service.lead_repository.organization_id).create_rule(
        rule_type="exact_name",
        pattern="Mega Chain Campinas",
        reason="Blocked during discovery",
    )

    reevaluated = service.evaluate_preview_exclusions(preview)
    blocked_item = next(item for item in reevaluated.items if item.candidate.business_name == "Mega Chain Campinas")

    assert provider_calls == ["loja de tintas"]
    assert blocked_item.exclusion.is_blocked is True
    assert blocked_item.exclusion.rule_type == "exact_name"
    assert blocked_item.exclusion.reason == "Blocked during discovery"

    response = service.import_preview(
        request=request,
        preview=reevaluated,
        selected_client_result_ids=[item.client_result_id or "" for item in reevaluated.items],
    )

    assert provider_calls == ["loja de tintas"]
    assert response.selected_items == 2
    assert response.saved_items == 1
    assert response.skipped_blocked == 1
    assert response.created_leads == 1
    assert response.updated_leads == 0
    assert len(response.saved_lead_ids) == 1
    assert response.batch.record_count == 1
    assert response.batch.lead_count == 1
    assert response.skipped_items[0].business_name == "Mega Chain Campinas"
    assert db_session.scalar(select(func.count(Lead.id))) == 1
    assert db_session.scalar(select(func.count(RawDiscoveryRecord.id))) == 1
    assert db_session.scalar(select(func.count(ActivityLog.id))) == 1


def test_discovery_enrich_preview_rechecks_exclusions_without_new_provider_call(db_session, monkeypatch) -> None:
    settings = Settings(APP_ENV="test", DATABASE_URL="sqlite://", GOOGLE_API_KEY="test-key")
    service = DiscoveryService(db_session, settings)
    request = DiscoverySearchRequest(
        search_terms=["loja de tintas"],
        location_query="Campinas, SP",
        radius_m=2500,
        max_results_per_term=5,
    )

    monkeypatch.setattr(
        service,
        "_resolve_location",
        lambda payload: GeocodedLocation(label="Campinas - SP, Brasil", latitude=-22.9056, longitude=-47.0608),
    )

    provider_calls: list[str] = []

    def fake_provider_search(**kwargs):
        provider_calls.append(kwargs["search_term"])
        return [
            ProviderLeadResult(
                candidate=_candidate(
                    "Casa Tinta Boa",
                    category="loja de tintas",
                    phone="+5511999991111",
                    city="Campinas",
                ),
                raw_payload={"id": "place-casa-tinta-boa"},
                provider_record_id="place-casa-tinta-boa",
                source_url="https://maps.google.com/?q=Casa+Tinta+Boa",
            )
        ]

    monkeypatch.setattr(service.provider, "search", fake_provider_search)

    preview = service.preview(request)
    preview_item = preview.items[0]
    assert preview_item.exclusion.is_blocked is False

    ExclusionRuleService(db_session, organization_id=service.lead_repository.organization_id).create_rule(
        rule_type="domain",
        pattern="bloqueada.example.com",
        reason="Blocked after preview enrichment",
    )

    def fake_enrich_preview_candidate(self, candidate):
        return (
            candidate.model_copy(update={"domain": "bloqueada.example.com"}),
            DiscoveryPreviewEnrichmentMetadata(email_found=True),
        )

    monkeypatch.setattr(
        "app.services.discovery.EnrichmentService.enrich_preview_candidate",
        fake_enrich_preview_candidate,
    )

    response = service.enrich_preview(
        preview=preview,
        client_result_ids=[preview_item.client_result_id or ""],
    )

    assert provider_calls == ["loja de tintas"]
    assert response.summary.requested == 1
    assert response.summary.processed == 1
    assert response.summary.success_count == 1
    assert response.summary.emails_found == 1
    assert response.summary.blocked_after_enrichment == 1
    assert response.preview.items[0].candidate.domain == "bloqueada.example.com"
    assert response.preview.items[0].exclusion.is_blocked is True
    assert response.preview.items[0].exclusion.rule_type == "domain"


def test_discovery_enrich_preview_handles_malformed_website_with_domain_rules(db_session) -> None:
    settings = Settings(APP_ENV="test", DATABASE_URL="sqlite://", GOOGLE_API_KEY="test-key")
    service = DiscoveryService(db_session, settings)
    ExclusionRuleService(db_session, organization_id=service.lead_repository.organization_id).create_rule(
        rule_type="domain",
        pattern="blocked.com",
        reason="Blocked domain",
    )
    db_session.commit()

    preview = service.evaluate_preview_exclusions(
        DiscoveryPreviewResponse(
            provider="google_places",
            resolved_location=ResolvedLocation(
                label="Campinas, SP",
                latitude=-22.9056,
                longitude=-47.0608,
            ),
            total_provider_results=1,
            items=[
                DiscoveryPreviewItem(
                    client_result_id="bad-url-1",
                    search_term="loja de tintas",
                    provider_record_id="place-bad-url-1",
                    source_url="https://maps.google.com/?q=Bad+Url+Store",
                    raw_payload={},
                    candidate=DiscoveryLeadCandidate(
                        business_name="Bad Url Store",
                        normalized_business_name=normalize_business_name("Bad Url Store") or "bad url store",
                        category="loja de tintas",
                        city="Campinas",
                        state="SP",
                        website="http://[invalid",
                        source_provider="google_places",
                        source_url="https://maps.google.com/?q=Bad+Url+Store",
                        google_maps_url="https://maps.google.com/?q=Bad+Url+Store",
                        google_place_id="place-bad-url-1",
                        lead_source_type="google_places",
                    ),
                )
            ],
        )
    )

    response = service.enrich_preview(
        preview=preview,
        client_result_ids=["bad-url-1"],
    )

    assert response.summary.requested == 1
    assert response.summary.processed == 1
    assert response.summary.success_count == 1
    assert response.summary.skipped_no_website == 1
    assert response.summary.errors == 0
    assert response.preview.items[0].candidate.website is None
    assert response.preview.items[0].enrichment is not None
    assert response.preview.items[0].enrichment.skipped_reason == "No public website."


def test_discovery_enrich_preview_keeps_request_alive_when_one_row_returns_bad_enrichment_payload(
    db_session,
    monkeypatch,
) -> None:
    settings = Settings(APP_ENV="test", DATABASE_URL="sqlite://", GOOGLE_API_KEY="test-key")
    service = DiscoveryService(db_session, settings)
    preview = DiscoveryPreviewResponse(
        provider="google_places",
        resolved_location=ResolvedLocation(
            label="Campinas, SP",
            latitude=-22.9056,
            longitude=-47.0608,
        ),
        total_provider_results=3,
        items=[
            DiscoveryPreviewItem(
                client_result_id="preview-good-1",
                search_term="loja de tintas",
                provider_record_id="place-good-1",
                source_url="https://maps.google.com/?q=Boa+1",
                raw_payload={},
                candidate=DiscoveryLeadCandidate(
                    business_name="Boa 1",
                    normalized_business_name=normalize_business_name("Boa 1") or "boa 1",
                    category="loja de tintas",
                    city="Campinas",
                    state="SP",
                    website="https://boa1.example.com",
                    source_provider="google_places",
                    source_url="https://maps.google.com/?q=Boa+1",
                    google_maps_url="https://maps.google.com/?q=Boa+1",
                    google_place_id="place-good-1",
                    lead_source_type="google_places",
                ),
            ),
            DiscoveryPreviewItem(
                client_result_id="preview-bad-1",
                search_term="loja de tintas",
                provider_record_id="place-bad-1",
                source_url="https://maps.google.com/?q=Ruim+1",
                raw_payload={},
                candidate=DiscoveryLeadCandidate(
                    business_name="Ruim 1",
                    normalized_business_name=normalize_business_name("Ruim 1") or "ruim 1",
                    category="loja de tintas",
                    city="Campinas",
                    state="SP",
                    website="https://ruim1.example.com",
                    source_provider="google_places",
                    source_url="https://maps.google.com/?q=Ruim+1",
                    google_maps_url="https://maps.google.com/?q=Ruim+1",
                    google_place_id="place-bad-1",
                    lead_source_type="google_places",
                ),
            ),
            DiscoveryPreviewItem(
                client_result_id="preview-good-2",
                search_term="loja de tintas",
                provider_record_id="place-good-2",
                source_url="https://maps.google.com/?q=Boa+2",
                raw_payload={},
                candidate=DiscoveryLeadCandidate(
                    business_name="Boa 2",
                    normalized_business_name=normalize_business_name("Boa 2") or "boa 2",
                    category="loja de tintas",
                    city="Campinas",
                    state="SP",
                    website="https://boa2.example.com",
                    source_provider="google_places",
                    source_url="https://maps.google.com/?q=Boa+2",
                    google_maps_url="https://maps.google.com/?q=Boa+2",
                    google_place_id="place-good-2",
                    lead_source_type="google_places",
                ),
            ),
        ],
    )

    def fake_enrich_preview_candidate(self, candidate):
        if candidate.business_name == "Ruim 1":
            return candidate, object()
        return (
            candidate.model_copy(update={"email": f"{candidate.normalized_business_name.replace(' ', '')}@example.com"}),
            DiscoveryPreviewEnrichmentMetadata(email_found=True),
        )

    monkeypatch.setattr(
        "app.services.discovery.EnrichmentService.enrich_preview_candidate",
        fake_enrich_preview_candidate,
    )

    response = service.enrich_preview(
        preview=preview,
        client_result_ids=["preview-good-1", "preview-bad-1", "preview-good-2"],
    )

    assert response.summary.requested == 3
    assert response.summary.processed == 3
    assert response.summary.success_count == 2
    assert response.summary.errors == 1
    assert response.summary.emails_found == 2
    assert response.summary.error_messages == ["Ruim 1: 'object' object has no attribute 'model_dump'"]
    by_id = {item.client_result_id: item for item in response.preview.items}
    assert by_id["preview-good-1"].candidate.email == "boa1@example.com"
    assert by_id["preview-good-1"].enrichment is not None
    assert by_id["preview-good-1"].enrichment.email_found is True
    assert by_id["preview-bad-1"].enrichment is not None
    assert by_id["preview-bad-1"].enrichment.success is False
    assert by_id["preview-bad-1"].enrichment.error_message == "'object' object has no attribute 'model_dump'"
    assert by_id["preview-good-2"].candidate.email == "boa2@example.com"
