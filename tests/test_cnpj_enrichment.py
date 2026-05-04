from __future__ import annotations

import pytest
import requests

from app.config import Settings
from app.models.lead import Lead
from app.schemas.lead import LeadDetail
from app.services.cnpj_enrichment import (
    CNPJA_OPEN_PUBLIC_BATCH_LIMIT_MESSAGE,
    CNPJEnrichmentService,
    INVALID_LEAD_CNPJ_REASON,
    NEEDS_REVIEW_REASON,
    NO_WEBSITE_AVAILABLE_REASON,
    NO_WEBSITE_CNPJ_REASON,
    SKIPPED_KNOWN_CNPJ_REASON,
    extract_cnpj_candidates_from_text,
    is_valid_cnpj,
)
from app.services.normalization import normalize_business_name
from app.services.providers.cnpja import (
    CNPJAProvider,
    CNPJAProviderError,
    CNPJANotFoundError,
    CNPJLookupResult,
    normalize_cnpj,
)
from app.services.providers.cnpj_ws import CNPJWSProvider


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        payload: dict | None = None,
        url: str | None = None,
        text: str = "",
        content_type: str = "application/json",
    ) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.url = url or "https://example.com"
        self.text = text
        self.headers = {"content-type": content_type}

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(response=self)


class FakeHTTPSession:
    def __init__(
        self,
        responses: dict[str, FakeResponse],
        *,
        default_status_code: int | None = None,
        default_content_type: str = "text/html; charset=utf-8",
    ) -> None:
        self.responses = responses
        self.default_status_code = default_status_code
        self.default_content_type = default_content_type
        self.get_calls: list[tuple[str, dict]] = []
        self.post_calls: list[tuple[str, dict]] = []

    def get(self, url: str, **kwargs) -> FakeResponse:
        self.get_calls.append((url, kwargs))
        if url in self.responses:
            response = self.responses[url]
            if isinstance(response, Exception):
                raise response
            return response
        if self.default_status_code is None:
            raise KeyError(url)
        return FakeResponse(
            url=url,
            text="<html><body>Not found</body></html>",
            status_code=self.default_status_code,
            content_type=self.default_content_type,
        )

    def post(self, url: str, **kwargs) -> FakeResponse:
        self.post_calls.append((url, kwargs))
        if url in self.responses:
            response = self.responses[url]
            if isinstance(response, Exception):
                raise response
            return response
        if self.default_status_code is None:
            raise KeyError(url)
        return FakeResponse(
            url=url,
            text="<html><body>Not found</body></html>",
            status_code=self.default_status_code,
            content_type=self.default_content_type,
        )


class FakeCNPJAProvider:
    def __init__(
        self,
        *,
        lookup_result: CNPJLookupResult | None = None,
        lookup_results_by_cnpj: dict[str, CNPJLookupResult] | None = None,
        lookup_not_found: set[str] | None = None,
        lookup_error: Exception | None = None,
        search_results: list[CNPJLookupResult] | None = None,
        search_error: Exception | None = None,
        http_session: FakeHTTPSession | None = None,
    ) -> None:
        self.lookup_result = lookup_result or _lookup_result()
        self.lookup_results_by_cnpj = lookup_results_by_cnpj or {}
        self.lookup_not_found = lookup_not_found or set()
        self.lookup_error = lookup_error
        self.search_results = search_results or []
        self.search_error = search_error
        self.http = http_session
        self.lookup_calls: list[str] = []
        self.search_calls: list[dict[str, str | None]] = []

    def lookup_known_cnpj(self, cnpj: str, strategy: str | None = None) -> CNPJLookupResult:
        del strategy
        self.lookup_calls.append(cnpj)
        if self.lookup_error is not None:
            raise self.lookup_error
        if cnpj in self.lookup_not_found:
            raise CNPJANotFoundError()
        return self.lookup_results_by_cnpj.get(cnpj, self.lookup_result)

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
        "CNPJ_LOOKUP_PROVIDER": "cnpja_open",
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
    source_provider: str = "cnpja_open",
    neighborhood: str | None = None,
) -> CNPJLookupResult:
    metadata = {"queried_via": source_provider}
    if neighborhood:
        metadata["neighborhood"] = neighborhood
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
        source_provider=source_provider,
        provider_record_id=cnpj,
        metadata=metadata,
    )


def test_normalize_cnpj_accepts_only_14_digits() -> None:
    assert normalize_cnpj("37.335.118/0001-80") == "37335118000180"
    assert normalize_cnpj("37335118000180") == "37335118000180"
    assert normalize_cnpj("123") is None
    assert normalize_cnpj(None) is None


def test_validate_cnpj_check_digits() -> None:
    assert is_valid_cnpj("37335118000180") is True
    assert is_valid_cnpj("11111111111111") is False
    assert is_valid_cnpj("37335118000181") is False


def test_extracts_formatted_cnpj_from_website_text() -> None:
    text = "Nosso CNPJ é 37.335.118/0001-80 e fica no rodapé."
    assert extract_cnpj_candidates_from_text(text) == ["37335118000180"]


def test_extracts_unformatted_cnpj_from_website_text() -> None:
    text = "Empresa registrada sob o número 37335118000180."
    assert extract_cnpj_candidates_from_text(text) == ["37335118000180"]


def test_extract_cnpj_rejects_cpf_length_values() -> None:
    text = "CPF 12345678901 e documento fiscal."
    assert extract_cnpj_candidates_from_text(text) == []


def test_extract_cnpj_rejects_invalid_check_digits() -> None:
    text = "CNPJ 37.335.118/0001-81"
    assert extract_cnpj_candidates_from_text(text) == []


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


def test_cnpj_ws_provider_builds_known_cnpj_url_and_maps_response() -> None:
    session = FakeHTTPSession(
        {
            "https://publica.cnpj.ws/cnpj/37335118000180": FakeResponse(
                payload={
                    "razao_social": "Oficina CNPJ LTDA",
                    "estabelecimento": {
                        "cnpj": "37.335.118/0001-80",
                        "nome_fantasia": "Oficina CNPJ",
                        "situacao_cadastral": "Ativa",
                        "cep": "13000-000",
                        "logradouro": "Rua Alfa",
                        "numero": "10",
                        "bairro": "Centro",
                        "email": "contato@oficina.com.br",
                        "ddd1": "11",
                        "telefone1": "33334444",
                        "atividade_principal": {"descricao": "Oficina mecanica"},
                        "cidade": {"nome": "Campinas"},
                        "estado": {"sigla": "SP"},
                    },
                }
            )
        }
    )
    provider = CNPJWSProvider(_settings(), http_session=session)

    result = provider.lookup_known_cnpj("37.335.118/0001-80")

    assert session.get_calls[0][0] == "https://publica.cnpj.ws/cnpj/37335118000180"
    assert result.cnpj == "37335118000180"
    assert result.legal_name == "Oficina CNPJ LTDA"
    assert result.trade_name == "Oficina CNPJ"
    assert result.registration_status == "Ativa"
    assert result.address == "Rua Alfa, 10"
    assert result.city == "Campinas"
    assert result.state == "SP"
    assert result.postal_code == "13000-000"
    assert result.phones == ["1133334444"]
    assert result.emails == ["contato@oficina.com.br"]
    assert result.primary_activity == "Oficina mecanica"


def test_cnpj_ws_provider_rejects_invalid_cnpj_before_request() -> None:
    session = FakeHTTPSession({}, default_status_code=None)
    provider = CNPJWSProvider(_settings(), http_session=session)

    with pytest.raises(CNPJANotFoundError, match="Invalid CNPJ"):
        provider.lookup_known_cnpj("123")

    assert session.get_calls == []


def test_cnpj_ws_provider_404_returns_not_found_safely() -> None:
    session = FakeHTTPSession(
        {"https://publica.cnpj.ws/cnpj/37335118000180": FakeResponse(status_code=404)},
        default_status_code=None,
    )
    provider = CNPJWSProvider(_settings(), http_session=session)

    with pytest.raises(CNPJANotFoundError):
        provider.lookup_known_cnpj("37335118000180")


def test_cnpj_ws_provider_429_returns_rate_limit_error_safely() -> None:
    session = FakeHTTPSession(
        {"https://publica.cnpj.ws/cnpj/37335118000180": FakeResponse(status_code=429)},
        default_status_code=None,
    )
    provider = CNPJWSProvider(_settings(), http_session=session)

    with pytest.raises(CNPJAProviderError, match="CNPJ.ws request hit the upstream usage limit"):
        provider.lookup_known_cnpj("37335118000180")


def test_cnpj_batch_large_without_api_key_fails_safely(db_session) -> None:
    leads = [_lead(cnpj=f"3733511800018{index}") for index in range(4)]
    db_session.add_all(leads)
    db_session.commit()

    service = CNPJEnrichmentService(db_session, _settings())

    with pytest.raises(CNPJAProviderError, match="CNPJA open lookup supports at most 3"):
        service.enrich_lead_ids([lead.id for lead in leads], actor="test")


def test_website_cnpj_batch_limit_fails_fast_for_large_selection(db_session) -> None:
    leads = [_lead(cnpj=None, website=f"https://empresa-{index}.example.com") for index in range(11)]
    db_session.add_all(leads)
    db_session.commit()

    service = CNPJEnrichmentService(db_session, _settings())

    with pytest.raises(CNPJAProviderError, match="Website-based CNPJ enrichment works better in smaller batches"):
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


def test_known_cnpj_enrichment_can_use_cnpj_ws_provider(db_session) -> None:
    lead = _lead(cnpj="37335118000180")
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    session = FakeHTTPSession(
        {
            "https://publica.cnpj.ws/cnpj/37335118000180": FakeResponse(
                payload={
                    "razao_social": "Oficina CNPJ LTDA",
                    "estabelecimento": {
                        "cnpj": "37335118000180",
                        "nome_fantasia": "Oficina CNPJ",
                        "situacao_cadastral": "Ativa",
                        "cep": "13000-000",
                        "logradouro": "Rua Alfa",
                        "numero": "10",
                        "cidade": {"nome": "Campinas"},
                        "estado": {"sigla": "SP"},
                    },
                }
            )
        },
        default_status_code=None,
    )
    provider = CNPJAProvider(
        _settings(CNPJ_LOOKUP_PROVIDER="cnpj_ws"),
        http_session=session,
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(CNPJ_LOOKUP_PROVIDER="cnpj_ws"),
        provider=provider,
    )

    response = service.enrich_lead_ids([lead.id], actor="test", force=True)
    db_session.refresh(lead)

    assert response.summary.matched_count == 1
    assert lead.cnpj == "37335118000180"
    assert lead.legal_name == "Oficina CNPJ LTDA"
    assert lead.cnpj_source_provider == "cnpj_ws"


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


def test_lead_without_cnpj_but_with_website_cnpj_gets_matched_after_provider_validation(db_session) -> None:
    lead = _lead(website="https://empresa.example.com", phone=None)
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    http_session = FakeHTTPSession(
        {
            "https://empresa.example.com/robots.txt": FakeResponse(
                url="https://empresa.example.com/robots.txt",
                text="User-agent: *\nAllow: /\n",
                content_type="text/plain",
            ),
            "https://empresa.example.com": FakeResponse(
                url="https://empresa.example.com",
                text="<html><body><a href=\"/contato\">Contato</a></body></html>",
                content_type="text/html; charset=utf-8",
            ),
            "https://empresa.example.com/": FakeResponse(
                url="https://empresa.example.com/",
                text="<html><body>Página inicial</body></html>",
                content_type="text/html; charset=utf-8",
            ),
            "https://empresa.example.com/contato": FakeResponse(
                url="https://empresa.example.com/contato",
                text="<html><body>CNPJ: 37.335.118/0001-80</body></html>",
                content_type="text/html; charset=utf-8",
            ),
        },
        default_status_code=404,
    )
    fake_provider = FakeCNPJAProvider(
        lookup_results_by_cnpj={
            "37335118000180": _lookup_result(
                source_provider="cnpja_open",
                phones=[],
            )
        },
        http_session=http_session,
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")
    db_session.refresh(lead)

    assert response.summary.matched_count == 1
    assert response.summary.no_cnpj_on_website_count == 0
    assert response.results[0].match_status == "matched"
    assert response.results[0].reason_code == "matched"
    assert lead.cnpj == "37335118000180"
    assert lead.legal_name == "Oficina CNPJ LTDA"
    assert lead.cnpj_metadata_json["matched_by"] == "website_cnpj"
    assert "https://empresa.example.com/contato" in lead.cnpj_metadata_json["candidate_summary"]["source_urls"]


def test_website_cnpj_with_mismatched_city_uf_does_not_auto_fill(db_session) -> None:
    lead = _lead(website="https://moveis.example.com", phone=None)
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    http_session = FakeHTTPSession(
        {
            "https://moveis.example.com/robots.txt": FakeResponse(
                url="https://moveis.example.com/robots.txt",
                text="User-agent: *\nAllow: /\n",
                content_type="text/plain",
            ),
            "https://moveis.example.com": FakeResponse(
                url="https://moveis.example.com",
                text="<html><body>CNPJ 37.335.118/0001-80</body></html>",
                content_type="text/html; charset=utf-8",
            ),
        },
        default_status_code=404,
    )
    fake_provider = FakeCNPJAProvider(
        lookup_results_by_cnpj={
            "37335118000180": _lookup_result(
                legal_name="Oficina CNPJ LTDA",
                trade_name="Oficina CNPJ",
                city="Curitiba",
                state="PR",
                source_provider="cnpja_open",
            )
        },
        http_session=http_session,
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")
    db_session.refresh(lead)

    assert response.summary.not_found_count == 1
    assert response.summary.validation_failed_count == 0
    assert response.summary.low_confidence_count == 1
    assert lead.cnpj is None
    assert lead.cnpj_match_status == "not_found"
    assert response.results[0].reason_code == "low_confidence"


def test_website_cnpj_medium_confidence_becomes_needs_review(db_session) -> None:
    lead = _lead(
        business_name="Clinica Bela",
        website="https://clinica.example.com",
        phone=None,
        whatsapp=None,
        address=None,
        postal_code=None,
        city=None,
        state=None,
    )
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    http_session = FakeHTTPSession(
        {
            "https://clinica.example.com/robots.txt": FakeResponse(
                url="https://clinica.example.com/robots.txt",
                text="User-agent: *\nAllow: /\n",
                content_type="text/plain",
            ),
            "https://clinica.example.com": FakeResponse(
                url="https://clinica.example.com",
                text="<html><body>CNPJ 37.335.118/0001-80</body></html>",
                content_type="text/html; charset=utf-8",
            ),
        },
        default_status_code=404,
    )
    fake_provider = FakeCNPJAProvider(
        lookup_results_by_cnpj={
            "37335118000180": _lookup_result(
                legal_name="Clinica Bela Ltda",
                trade_name="Clinica Bela",
                city=None,
                state=None,
                address=None,
                postal_code=None,
                website=None,
                phones=[],
                source_provider="cnpja_open",
            )
        },
        http_session=http_session,
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")
    db_session.refresh(lead)

    assert response.summary.needs_review_count == 1
    assert response.results[0].match_status == "needs_review"
    assert response.results[0].reason_code == "needs_review"
    assert response.results[0].skipped_reason == NEEDS_REVIEW_REASON
    assert lead.cnpj is None
    assert lead.cnpj_match_status == "needs_review"


def test_website_without_visible_cnpj_returns_reason_count(db_session) -> None:
    lead = _lead(website="https://sem-cnpj.example.com")
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    http_session = FakeHTTPSession(
        {
            "https://sem-cnpj.example.com/robots.txt": FakeResponse(
                url="https://sem-cnpj.example.com/robots.txt",
                text="User-agent: *\nAllow: /\n",
                content_type="text/plain",
            ),
            "https://sem-cnpj.example.com": FakeResponse(
                url="https://sem-cnpj.example.com",
                text="<html><body>Fale conosco pelo formulário.</body></html>",
                content_type="text/html; charset=utf-8",
            ),
        },
        default_status_code=404,
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(),
        provider=FakeCNPJAProvider(http_session=http_session),  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")

    assert response.summary.not_found_count == 1
    assert response.summary.no_cnpj_on_website_count == 1
    assert response.results[0].reason_code == "no_cnpj_on_website"


def test_slow_website_returns_timeout_reason(db_session) -> None:
    lead = _lead(website="https://lento.example.com")
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    http_session = FakeHTTPSession(
        {
            "https://lento.example.com/robots.txt": FakeResponse(
                url="https://lento.example.com/robots.txt",
                text="User-agent: *\nAllow: /\n",
                content_type="text/plain",
            ),
            "https://lento.example.com": requests.Timeout("Read timed out"),
            "https://lento.example.com/": requests.Timeout("Read timed out"),
            "https://lento.example.com/contato": requests.Timeout("Read timed out"),
            "https://lento.example.com/sobre": requests.Timeout("Read timed out"),
            "https://lento.example.com/politica-de-privacidade": requests.Timeout("Read timed out"),
        },
        default_status_code=None,
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(),
        provider=FakeCNPJAProvider(http_session=http_session),  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")

    assert response.summary.website_timeout_count == 1
    assert response.results[0].reason_code == "website_timeout"


def test_same_domain_reused_in_batch_uses_cached_crawl(db_session) -> None:
    lead_a = _lead(business_name="Empresa A", website="https://cache.example.com")
    lead_b = _lead(business_name="Empresa B", website="https://cache.example.com")
    db_session.add_all([lead_a, lead_b])
    db_session.commit()
    db_session.refresh(lead_a)
    db_session.refresh(lead_b)

    http_session = FakeHTTPSession(
        {
            "https://cache.example.com/robots.txt": FakeResponse(
                url="https://cache.example.com/robots.txt",
                text="User-agent: *\nAllow: /\n",
                content_type="text/plain",
            ),
            "https://cache.example.com": FakeResponse(
                url="https://cache.example.com",
                text="<html><body>CNPJ 37.335.118/0001-80</body></html>",
                content_type="text/html; charset=utf-8",
            ),
        },
        default_status_code=404,
    )
    fake_provider = FakeCNPJAProvider(
        lookup_results_by_cnpj={"37335118000180": _lookup_result(phones=[])},
        http_session=http_session,
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    service.enrich_lead_ids([lead_a.id, lead_b.id], actor="test")

    site_calls = [url for url, _ in http_session.get_calls if url.startswith("https://cache.example.com")]
    assert site_calls.count("https://cache.example.com") == 1
    assert fake_provider.lookup_calls == ["37335118000180"]


def test_same_cnpj_candidate_reused_in_batch_validates_once(db_session) -> None:
    lead_a = _lead(business_name="Empresa A", website="https://a.example.com")
    lead_b = _lead(business_name="Empresa B", website="https://b.example.com")
    db_session.add_all([lead_a, lead_b])
    db_session.commit()
    db_session.refresh(lead_a)
    db_session.refresh(lead_b)

    http_session = FakeHTTPSession(
        {
            "https://a.example.com/robots.txt": FakeResponse(
                url="https://a.example.com/robots.txt",
                text="User-agent: *\nAllow: /\n",
                content_type="text/plain",
            ),
            "https://a.example.com": FakeResponse(
                url="https://a.example.com",
                text="<html><body>CNPJ 37.335.118/0001-80</body></html>",
                content_type="text/html; charset=utf-8",
            ),
            "https://b.example.com/robots.txt": FakeResponse(
                url="https://b.example.com/robots.txt",
                text="User-agent: *\nAllow: /\n",
                content_type="text/plain",
            ),
            "https://b.example.com": FakeResponse(
                url="https://b.example.com",
                text="<html><body>CNPJ 37.335.118/0001-80</body></html>",
                content_type="text/html; charset=utf-8",
            ),
        },
        default_status_code=404,
    )
    fake_provider = FakeCNPJAProvider(
        lookup_results_by_cnpj={"37335118000180": _lookup_result(phones=[])},
        http_session=http_session,
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    service.enrich_lead_ids([lead_a.id, lead_b.id], actor="test")

    assert fake_provider.lookup_calls == ["37335118000180"]


def test_no_website_and_no_cnpj_returns_not_found_safely(db_session) -> None:
    lead = _lead(cnpj=None, website=None)
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    fake_provider = FakeCNPJAProvider()
    service = CNPJEnrichmentService(
        db_session,
        _settings(),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")
    db_session.refresh(lead)

    assert response.summary.not_found_count == 1
    assert response.summary.no_website_count == 1
    assert response.results[0].reason_code == "skipped_no_website"
    assert response.results[0].skipped_reason == NO_WEBSITE_AVAILABLE_REASON
    assert fake_provider.lookup_calls == []
    assert fake_provider.search_calls == []
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
    assert response.json()["detail"] == CNPJA_OPEN_PUBLIC_BATCH_LIMIT_MESSAGE


def test_no_cpf_fields_were_added() -> None:
    assert "cpf" not in Lead.__table__.c
    assert "cpf" not in LeadDetail.model_fields
