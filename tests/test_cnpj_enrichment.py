from __future__ import annotations

import pytest

from app.config import Settings
from app.models.lead import Lead
from app.schemas.lead import LeadDetail
from app.services.cnpj_enrichment import (
    CNPJEnrichmentService,
    INVALID_LEAD_CNPJ_REASON,
    MISSING_COMPANY_SEARCH_REASON,
    NEEDS_REVIEW_REASON,
    SKIPPED_KNOWN_CNPJ_REASON,
)
from app.services.normalization import normalize_business_name
from app.services.providers.cnpja import (
    CNPJAProvider,
    CNPJAProviderError,
    CNPJLookupResult,
    MISSING_CNPJA_API_KEY_BATCH_MESSAGE,
    normalize_cnpj,
)


class FakeResponse:
    def __init__(self, *, status_code: int = 200, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(response=self)


class FakeHTTPSession:
    def __init__(self, responses: dict[str, FakeResponse]) -> None:
        self.responses = responses
        self.post_calls: list[tuple[str, dict]] = []

    def get(self, url: str, **kwargs) -> FakeResponse:
        return self.responses[url]

    def post(self, url: str, **kwargs) -> FakeResponse:
        self.post_calls.append((url, kwargs))
        return self.responses[url]


class FakeCNPJAProvider:
    def __init__(
        self,
        *,
        lookup_result: CNPJLookupResult | None = None,
        search_results: list[CNPJLookupResult] | None = None,
        search_error: Exception | None = None,
    ) -> None:
        self.lookup_result = lookup_result or _lookup_result()
        self.search_results = search_results or []
        self.search_error = search_error
        self.lookup_calls: list[str] = []
        self.search_calls: list[dict[str, str | None]] = []

    def lookup_known_cnpj(self, cnpj: str, strategy: str | None = None) -> CNPJLookupResult:
        self.lookup_calls.append(cnpj)
        return self.lookup_result

    def search_companies(
        self,
        *,
        business_name: str,
        city: str | None = None,
        state: str | None = None,
        postal_code: str | None = None,
        website: str | None = None,
        phone: str | None = None,
        whatsapp: str | None = None,
        address: str | None = None,
        neighborhood: str | None = None,
    ) -> list[CNPJLookupResult]:
        self.search_calls.append(
            {
                "business_name": business_name,
                "city": city,
                "state": state,
                "postal_code": postal_code,
                "website": website,
                "phone": phone,
                "whatsapp": whatsapp,
                "address": address,
                "neighborhood": neighborhood,
            }
        )
        if self.search_error is not None:
            raise self.search_error
        return self.search_results


def _settings(**overrides) -> Settings:
    base = {
        "APP_ENV": "test",
        "DATABASE_URL": "sqlite://",
        "EXPORT_DIR": "./data/exports",
        "GOOGLE_API_KEY": "",
    }
    base.update(overrides)
    return Settings(**base)


def _lead(
    *,
    business_name: str = "Oficina CNPJ",
    cnpj: str | None = None,
    legal_name: str | None = None,
    match_status: str = "unknown",
    website: str | None = "https://oficina-cnpj.com.br",
    phone: str | None = "(11) 3333-4444",
    whatsapp: str | None = None,
    address: str | None = "Rua Alfa, 10",
    postal_code: str | None = "13000-000",
    city: str | None = "Campinas",
    state: str | None = "SP",
    neighborhood: str | None = "Centro",
) -> Lead:
    return Lead(
        business_name=business_name,
        normalized_business_name=normalize_business_name(business_name) or business_name.lower(),
        category="oficina mecanica",
        city=city,
        state=state,
        neighborhood=neighborhood,
        address=address,
        postal_code=postal_code,
        website=website,
        phone=phone,
        whatsapp=whatsapp,
        cnpj=cnpj,
        legal_name=legal_name,
        cnpj_match_status=match_status,
    )


def _lookup_result(
    *,
    cnpj: str = "37335118000180",
    legal_name: str | None = "Oficina CNPJ LTDA",
    trade_name: str | None = "Oficina CNPJ",
    city: str | None = "Campinas",
    state: str | None = "SP",
    address: str | None = "Rua Alfa, 10",
    postal_code: str | None = "13000-000",
    website: str | None = "https://oficina-cnpj.com.br",
    phones: list[str] | None = None,
) -> CNPJLookupResult:
    return CNPJLookupResult(
        cnpj=cnpj,
        legal_name=legal_name,
        trade_name=trade_name,
        registration_status="Ativa",
        address=address,
        city=city,
        state=state,
        postal_code=postal_code,
        website=website,
        domain="oficina-cnpj.com.br" if website else None,
        phones=phones or ["1133334444"],
        emails=["contato@oficina.com.br"],
        primary_activity="Oficina mecanica",
        source_provider="cnpja",
        provider_record_id=cnpj,
        metadata={"queried_via": "cnpja"},
    )


def test_normalize_cnpj_accepts_only_14_digits() -> None:
    assert normalize_cnpj("37.335.118/0001-80") == "37335118000180"
    assert normalize_cnpj("37335118000180") == "37335118000180"
    assert normalize_cnpj("123") is None
    assert normalize_cnpj(None) is None


def test_lookup_known_cnpj_maps_open_api_payload() -> None:
    provider = CNPJAProvider(
        _settings(),
        http_session=FakeHTTPSession(
            {
                "https://open.cnpja.com/office/37335118000180": FakeResponse(
                    payload={
                        "office": {
                            "taxId": "37335118000180",
                            "alias": "Oficina CNPJ",
                            "status": {"text": "Ativa"},
                            "address": {
                                "street": "Rua Alfa",
                                "number": "10",
                                "city": "Campinas",
                                "state": "SP",
                                "zip": "13000-000",
                            },
                            "phones": [{"full": "1133334444"}],
                            "emails": ["contato@oficina.com.br"],
                            "website": "https://oficina-cnpj.com.br",
                            "mainActivity": {"text": "Oficina mecanica"},
                        },
                        "company": {"name": "Oficina CNPJ LTDA"},
                    }
                )
            }
        ),
    )

    result = provider.lookup_known_cnpj("37.335.118/0001-80")

    assert result.cnpj == "37335118000180"
    assert result.legal_name == "Oficina CNPJ LTDA"
    assert result.trade_name == "Oficina CNPJ"
    assert result.registration_status == "Ativa"
    assert result.city == "Campinas"
    assert result.state == "SP"
    assert result.postal_code == "13000-000"
    assert result.website == "https://oficina-cnpj.com.br"
    assert result.domain == "oficina-cnpj.com.br"
    assert result.phones == ["1133334444"]
    assert result.emails == ["contato@oficina.com.br"]


def test_cnpj_batch_large_without_api_key_fails_safely(db_session) -> None:
    leads = [_lead(cnpj=f"3733511800018{index}") for index in range(4)]
    db_session.add_all(leads)
    db_session.commit()

    service = CNPJEnrichmentService(db_session, _settings())

    with pytest.raises(CNPJAProviderError, match="CNPJA_API_KEY"):
        service.enrich_lead_ids([lead.id for lead in leads], actor="test")


def test_cnpj_enrichment_skips_confirmed_cnpj_unless_force(db_session) -> None:
    lead = _lead(cnpj="37335118000180", legal_name="Oficina CNPJ LTDA", match_status="matched")
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    fake_provider = FakeCNPJAProvider()
    service = CNPJEnrichmentService(
        db_session,
        _settings(),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    skipped = service.enrich_lead_ids([lead.id], actor="test")
    forced = service.enrich_lead_ids([lead.id], actor="test", force=True)

    assert skipped.summary.skipped_known_count == 1
    assert skipped.results[0].skipped_reason == SKIPPED_KNOWN_CNPJ_REASON
    assert fake_provider.lookup_calls == ["37335118000180"]
    assert forced.summary.matched_count == 1
    assert forced.results[0].match_status == "matched"


def test_cnpj_enrichment_does_not_overwrite_good_data_with_blanks(db_session) -> None:
    lead = _lead(cnpj="37335118000180", legal_name="Razao Social Existente")
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    service = CNPJEnrichmentService(
        db_session,
        _settings(),
        provider=FakeCNPJAProvider(lookup_result=_lookup_result(legal_name=None)),  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test", force=True)
    db_session.refresh(lead)

    assert response.summary.matched_count == 1
    assert lead.legal_name == "Razao Social Existente"


def test_lead_without_cnpj_attempts_provider_search_when_enabled(db_session) -> None:
    lead = _lead(business_name="Loja Exemplo", website=None, phone=None, postal_code=None)
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    fake_provider = FakeCNPJAProvider(search_results=[_lookup_result(trade_name="Loja Exemplo")])
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJA_API_KEY="key",
            CNPJA_SEARCH_ENDPOINT="https://cnpja.local/search",
            CNPJA_ENABLE_COMPANY_SEARCH=True,
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    service.enrich_lead_ids([lead.id], actor="test")

    assert len(fake_provider.search_calls) == 1
    assert fake_provider.search_calls[0]["business_name"] == "Loja Exemplo"
    assert fake_provider.search_calls[0]["city"] == "Campinas"
    assert fake_provider.search_calls[0]["state"] == "SP"


def test_high_confidence_candidate_fills_cnpj_and_legal_name(db_session) -> None:
    lead = _lead()
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    candidate = _lookup_result()
    fake_provider = FakeCNPJAProvider(lookup_result=candidate, search_results=[candidate])
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJA_API_KEY="key",
            CNPJA_SEARCH_ENDPOINT="https://cnpja.local/search",
            CNPJA_ENABLE_COMPANY_SEARCH=True,
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")
    db_session.refresh(lead)

    assert response.summary.matched_count == 1
    assert response.results[0].match_status == "matched"
    assert lead.cnpj == "37335118000180"
    assert lead.legal_name == "Oficina CNPJ LTDA"
    assert lead.cnpj_match_confidence == 1.0
    assert fake_provider.lookup_calls == ["37335118000180"]


def test_medium_confidence_candidate_marks_needs_review_without_filling_cnpj(db_session) -> None:
    lead = _lead(
        business_name="Clinica Bela",
        website=None,
        phone=None,
        whatsapp=None,
        address="Rua Alfa, 10",
        postal_code=None,
        city="Campinas",
        state="SP",
    )
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    candidate = _lookup_result(
        legal_name="Clinica Bela Ltda",
        trade_name="Clinica Bela",
        website=None,
        phones=[],
    )
    fake_provider = FakeCNPJAProvider(search_results=[candidate])
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJA_API_KEY="key",
            CNPJA_SEARCH_ENDPOINT="https://cnpja.local/search",
            CNPJA_ENABLE_COMPANY_SEARCH=True,
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")
    db_session.refresh(lead)

    assert response.summary.needs_review_count == 1
    assert response.results[0].match_status == "needs_review"
    assert response.results[0].skipped_reason == NEEDS_REVIEW_REASON
    assert lead.cnpj is None
    assert lead.cnpj_match_status == "needs_review"
    assert lead.cnpj_metadata_json["candidate_summary"]["cnpj"] == "37335118000180"


def test_low_confidence_name_only_match_marks_not_found(db_session) -> None:
    lead = _lead(
        business_name="Restaurante Boa Mesa",
        website=None,
        phone=None,
        whatsapp=None,
        address=None,
        postal_code=None,
        city="Campinas",
        state="SP",
    )
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    candidate = _lookup_result(
        legal_name="Restaurante Boa Mesa Ltda",
        trade_name="Restaurante Boa Mesa",
        address=None,
        website=None,
        phones=[],
    )
    fake_provider = FakeCNPJAProvider(search_results=[candidate])
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJA_API_KEY="key",
            CNPJA_SEARCH_ENDPOINT="https://cnpja.local/search",
            CNPJA_ENABLE_COMPANY_SEARCH=True,
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")
    db_session.refresh(lead)

    assert response.summary.not_found_count == 1
    assert response.results[0].match_status == "not_found"
    assert lead.cnpj is None
    assert lead.cnpj_match_status == "not_found"


def test_different_city_state_match_does_not_auto_fill(db_session) -> None:
    lead = _lead(business_name="Moveis Alfa")
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    candidate = _lookup_result(
        legal_name="Moveis Alfa Ltda",
        trade_name="Moveis Alfa",
        city="Curitiba",
        state="PR",
        phones=["1133334444"],
        website="https://oficina-cnpj.com.br",
    )
    fake_provider = FakeCNPJAProvider(search_results=[candidate])
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJA_API_KEY="key",
            CNPJA_SEARCH_ENDPOINT="https://cnpja.local/search",
            CNPJA_ENABLE_COMPANY_SEARCH=True,
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")
    db_session.refresh(lead)

    assert response.summary.not_found_count == 1
    assert lead.cnpj is None
    assert lead.cnpj_match_status == "not_found"


def test_missing_provider_search_config_marks_not_found_safely(db_session) -> None:
    lead = _lead(cnpj=None)
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    service = CNPJEnrichmentService(
        db_session,
        _settings(),
        provider=FakeCNPJAProvider(),  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")
    db_session.refresh(lead)

    assert response.summary.not_found_count == 1
    assert response.results[0].skipped_reason == MISSING_COMPANY_SEARCH_REASON
    assert lead.cnpj_match_status == "not_found"


def test_invalid_saved_cnpj_stays_needs_review(db_session) -> None:
    lead = _lead(cnpj="123", match_status="unknown")
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    service = CNPJEnrichmentService(
        db_session,
        _settings(),
        provider=FakeCNPJAProvider(),  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")

    assert response.summary.needs_review_count == 1
    assert response.results[0].skipped_reason == INVALID_LEAD_CNPJ_REASON


def test_cnpj_batch_endpoint_returns_summary(client, db_session, monkeypatch) -> None:
    lead = _lead(cnpj="37335118000180")
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    def fake_lookup(self, cnpj: str, strategy: str | None = None) -> CNPJLookupResult:
        return _lookup_result()

    monkeypatch.setattr(CNPJAProvider, "lookup_known_cnpj", fake_lookup)

    response = client.post("/leads/batch/enrich-cnpj", json={"lead_ids": [lead.id]})

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["matched_count"] == 1
    assert payload["results"][0]["cnpj"] == "37335118000180"
    assert payload["results"][0]["legal_name"] == "Oficina CNPJ LTDA"


def test_cnpj_batch_endpoint_without_key_returns_safe_error(client, db_session) -> None:
    leads = [_lead(cnpj=f"3733511800018{index}") for index in range(4)]
    db_session.add_all(leads)
    db_session.commit()

    response = client.post("/leads/batch/enrich-cnpj", json={"lead_ids": [lead.id for lead in leads]})

    assert response.status_code == 503
    assert response.json()["detail"] == MISSING_CNPJA_API_KEY_BATCH_MESSAGE


def test_no_cpf_fields_were_added() -> None:
    assert "cpf" not in Lead.__table__.c
    assert "cpf" not in LeadDetail.model_fields
