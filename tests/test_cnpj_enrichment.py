from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
import requests

from app.config import Settings
from app.models.base import utcnow
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
from app.services.enrichment import EnrichmentService
from app.services.geo.ibge_municipalities import lookup_ibge_municipality_code
from app.services.normalization import normalize_business_name
from app.services.providers.cnpja import (
    CNPJAProvider,
    CNPJAProviderError,
    CNPJANotFoundError,
    CNPJLookupResult,
    CompanySearchVariantGroups,
    build_company_search_name_variant_groups,
    build_company_search_name_variants,
    normalize_cnpj,
)
from app.services.providers.cnpjota import CNPJotaProvider
from app.services.providers.cnpj_ws import CNPJWSProvider


REPO_ROOT = Path(__file__).resolve().parents[1]


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
        search_results_sequence: list[list[CNPJLookupResult] | Exception] | None = None,
        search_metadata: dict[str, object] | None = None,
        search_metadata_sequence: list[dict[str, object] | None] | None = None,
        http_session: FakeHTTPSession | None = None,
    ) -> None:
        self.lookup_result = lookup_result or _lookup_result()
        self.lookup_results_by_cnpj = lookup_results_by_cnpj or {}
        self.lookup_not_found = lookup_not_found or set()
        self.lookup_error = lookup_error
        self.search_results = search_results or []
        self.search_error = search_error
        self.search_results_sequence = search_results_sequence or []
        self.search_metadata = search_metadata
        self.search_metadata_sequence = search_metadata_sequence or []
        self.last_company_search_metadata: dict[str, object] | None = None
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
        current_call_index = len(self.search_calls) - 1
        if current_call_index < len(self.search_metadata_sequence):
            self.last_company_search_metadata = self.search_metadata_sequence[current_call_index]
        else:
            self.last_company_search_metadata = self.search_metadata
        if self.search_error is not None:
            raise self.search_error
        if current_call_index < len(self.search_results_sequence):
            planned_result = self.search_results_sequence[current_call_index]
            if isinstance(planned_result, Exception):
                raise planned_result
            return planned_result
        return self.search_results


def _settings(**overrides) -> Settings:
    base = {
        "APP_ENV": "test",
        "DATABASE_URL": "sqlite://",
        "EXPORT_DIR": "./data/exports",
        "GOOGLE_API_KEY": "",
        "CNPJ_LOOKUP_PROVIDER": "cnpja_open",
        "CNPJ_COMPANY_SEARCH_ENABLED": False,
        "CNPJ_COMPANY_SEARCH_PROVIDER": "cnpja_commercial",
        "CNPJA_API_KEY": "",
        "CNPJA_API_BASE_URL": "",
        "CNPJA_ENABLE_COMPANY_SEARCH": False,
        "CNPJA_SEARCH_ENDPOINT": "",
        "CNPJ_WS_PREMIUM_TOKEN": "",
        "CNPJOTA_TOKEN": "",
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
    primary_activity: str | None = "Oficina mecanica",
    metadata_extra: dict[str, object] | None = None,
) -> CNPJLookupResult:
    metadata = {"queried_via": source_provider}
    if neighborhood:
        metadata["neighborhood"] = neighborhood
    if metadata_extra:
        metadata.update(metadata_extra)
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
        primary_activity=primary_activity,
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


def test_build_company_search_name_variants_strips_noisy_google_name_terms() -> None:
    variants = build_company_search_name_variants("Baby's Pet Shop e Banho e Tosa", max_variants=5)

    assert variants[0] == "Babys Pet Shop e Banho e Tosa"
    assert "Babys Pet Shop" in variants
    assert "Babys" in variants
    assert "Pet Shop" not in variants


def test_build_company_search_name_variants_splits_separators_and_dedupes() -> None:
    assert build_company_search_name_variants("Pet Shop Bela Vista | Banho Carinhoso", max_variants=4) == [
        "Pet Shop Bela Vista Banho Carinhoso",
        "Pet Shop Bela Vista",
        "Bela Vista",
        "Banho Carinhoso",
    ]


def test_build_company_search_name_variants_keeps_low_priority_brand_fallbacks_limited() -> None:
    variants = build_company_search_name_variants("Pet Space do Bixiga", max_variants=4)

    assert variants[:3] == [
        "Pet Space do Bixiga",
        "Pet Space",
        "Bixiga",
    ]
    assert len(variants) <= 4


def test_build_company_search_name_variants_extracts_chain_and_branch_fallbacks() -> None:
    assert build_company_search_name_variants("Cobasi Londrina Centro", max_variants=4) == [
        "Cobasi Londrina Centro",
        "Cobasi Londrina",
        "Cobasi",
        "Cobasi Centro",
    ]

    assert build_company_search_name_variants("Petz Catuaí Londrina", max_variants=4) == [
        "Petz Catuai Londrina",
        "Petz Catuai",
        "Petz",
    ]


def test_build_company_search_name_variants_extracts_brand_from_noisy_branch_name() -> None:
    variants = build_company_search_name_variants(
        "Empório dos Animais Pet Shop - Av. Higienópolis",
        max_variants=5,
    )

    assert "Emporio dos Animais Pet Shop" in variants
    assert "Emporio dos Animais" in variants
    assert "Emporio Animais" in variants
    assert "AV Higienopolis" not in variants


def test_build_company_search_name_variants_avoids_generic_only_queries() -> None:
    variants = build_company_search_name_variants("AGRO BAGGIO PETSHOP", max_variants=5)

    assert "Agro Baggio Petshop" in variants
    assert "Baggio Petshop" in variants
    assert "Baggio" in variants
    assert "Petshop" not in variants


def test_build_company_search_name_variant_groups_split_alias_and_names() -> None:
    groups = build_company_search_name_variant_groups("Cobasi Londrina Centro", max_variants=4)

    assert groups.alias_variants[:2] == ["Cobasi", "Cobasi Londrina"]
    assert groups.names_variants == [
        "Cobasi Londrina Centro",
        "Cobasi Londrina",
        "Cobasi",
        "Cobasi Centro",
    ]
    assert groups.legal_name_variants == []


def test_build_company_search_name_variant_groups_supports_brand_fallbacks() -> None:
    groups = build_company_search_name_variant_groups("Petz Catuaí Londrina", max_variants=4)

    assert groups.alias_variants[:2] == ["Petz", "Petz Catuai"]
    assert groups.names_variants[:3] == ["Petz Catuai Londrina", "Petz Catuai", "Petz"]


def test_build_company_search_name_variant_groups_supports_legal_names() -> None:
    groups = build_company_search_name_variant_groups(
        "Tecnocell Comercio e Servicos LTDA",
        max_variants=4,
    )

    assert groups.alias_variants
    assert "Tecnocell Comercio e Servicos Ltda" in groups.legal_name_variants


def test_ibge_municipality_lookup_maps_curitiba_pr() -> None:
    assert lookup_ibge_municipality_code("Curitiba", "PR") == "4106902"


def test_ibge_municipality_lookup_maps_londrina_pr() -> None:
    assert lookup_ibge_municipality_code("Londrina", "PR") == "4113700"


def test_ibge_municipality_lookup_maps_itu_sp() -> None:
    assert lookup_ibge_municipality_code("Itu", "SP") == "3523909"


def test_ibge_municipality_lookup_maps_laguna_sc() -> None:
    assert lookup_ibge_municipality_code("Laguna", "SC") == "4209409"


def test_ibge_municipality_lookup_maps_sao_paulo_sp() -> None:
    assert lookup_ibge_municipality_code("São Paulo", "SP") == "3550308"


def test_ibge_municipality_lookup_is_accent_insensitive() -> None:
    assert lookup_ibge_municipality_code("Sao Paulo", "SP") == "3550308"


def test_ibge_municipality_lookup_accepts_city_with_state_suffix() -> None:
    assert lookup_ibge_municipality_code("Curitiba, PR") == "4106902"


def test_ibge_municipality_lookup_returns_none_for_unknown_city() -> None:
    assert lookup_ibge_municipality_code("Cidade Inventada", "SP") is None


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


def test_cnpja_commercial_search_builds_office_endpoint_and_auth_header() -> None:
    session = FakeHTTPSession(
        {
            "https://api.cnpja.com/office": FakeResponse(
                payload={
                    "records": [
                        {
                            "taxId": "17247065000139",
                            "company": {"name": "Casa Falci Ltda"},
                            "alias": "Casa Falci",
                            "status": {"id": 2, "text": "Ativa"},
                            "address": {
                                "street": "Rua Beta",
                                "number": "45",
                                "district": "Centro",
                                "city": "Campinas",
                                "state": "SP",
                                "zip": "13000000",
                            },
                            "phones": [{"area": "19", "number": "32348887"}],
                            "emails": [{"address": "contato@casafalci.com.br"}],
                            "mainActivity": {"id": 4759899, "text": "Comercio varejista"},
                        }
                    ]
                }
            )
        },
        default_status_code=None,
    )
    provider = CNPJAProvider(
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpja_commercial",
            CNPJA_API_KEY="cnpja-key",
            CNPJA_API_BASE_URL="https://api.cnpja.com",
        ),
        http_session=session,
    )

    results = provider.search_companies(
        business_name="Casa Falci",
        city="Campinas",
        state="SP",
        postal_code="13000-000",
        neighborhood="Centro",
        phone="(19) 3234-8887",
    )

    assert session.get_calls[0][0] == "https://api.cnpja.com/office"
    assert session.get_calls[0][1]["headers"]["Authorization"] == "cnpja-key"
    assert session.get_calls[0][1]["headers"]["Accept"] == "application/json"
    assert session.get_calls[0][1]["params"]["limit"] == "10"
    assert session.get_calls[0][1]["params"]["alias.in"] == "Casa Falci,Falci"
    assert "names.in" not in session.get_calls[0][1]["params"]
    assert session.get_calls[0][1]["params"]["status.id.in"] == "2"
    assert session.get_calls[0][1]["params"]["address.state.in"] == "SP"
    assert session.get_calls[0][1]["params"]["address.municipality.in"] == "3509502"
    assert "address.zip.in" not in session.get_calls[0][1]["params"]
    assert "address.district.in" not in session.get_calls[0][1]["params"]
    assert "phones.area.in" not in session.get_calls[0][1]["params"]
    assert "mainActivity.id.in" not in session.get_calls[0][1]["params"]
    assert provider.last_company_search_metadata is not None
    assert provider.last_company_search_metadata["searched_city"] == "Campinas"
    assert provider.last_company_search_metadata["searched_municipality_code"] == "3509502"
    assert provider.last_company_search_metadata["municipality_mapping_found"] is True
    assert provider.last_company_search_metadata["matched_attempt_mode"] == "alias"
    assert results[0].cnpj == "17247065000139"
    assert results[0].legal_name == "Casa Falci Ltda"
    assert results[0].trade_name == "Casa Falci"
    assert results[0].city == "Campinas"
    assert results[0].state == "SP"
    assert results[0].postal_code == "13000000"
    assert results[0].phones == ["1932348887"]
    assert results[0].emails == ["contato@casafalci.com.br"]
    assert results[0].primary_activity == "Comercio varejista"
    assert results[0].source_provider == "cnpja_commercial"
    assert results[0].metadata["company_search_query_mode"] == "alias"


def test_cnpja_commercial_search_uses_alias_first_and_names_second_when_strong_filters_exist() -> None:
    session = FakeHTTPSession(
        {
            "https://api.cnpja.com/office": FakeResponse(payload={"records": []})
        },
        default_status_code=None,
    )
    provider = CNPJAProvider(
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpja_commercial",
            CNPJA_API_KEY="cnpja-key",
            CNPJA_API_BASE_URL="https://api.cnpja.com",
            CNPJA_NAME_VARIANT_LIMIT=4,
            CNPJA_MAX_SEARCH_ATTEMPTS_PER_LEAD=2,
        ),
        http_session=session,
    )

    results = provider.search_companies(
        business_name="Pet Shop Bela Vista | Banho Carinhoso",
        city="Londrina",
        state="SP",
        phone="(43) 3322-0000",
    )

    assert results == []
    assert session.get_calls[0][1]["params"]["alias.in"] == "Pet Shop Bela Vista,Bela Vista,Banho Carinhoso"
    assert session.get_calls[1][1]["params"]["names.in"] == (
        "Pet Shop Bela Vista Banho Carinhoso,Pet Shop Bela Vista,Bela Vista,Banho Carinhoso"
    )
    assert provider.last_company_search_metadata is not None
    assert provider.last_company_search_metadata["cnpja_zero_candidates"] is True
    assert provider.last_company_search_metadata["search_attempts_count"] == 2
    assert provider.last_company_search_metadata["searched_names"] == [
        "Pet Shop Bela Vista Banho Carinhoso",
        "Pet Shop Bela Vista",
        "Bela Vista",
        "Banho Carinhoso",
    ]


def test_cnpja_commercial_does_not_run_second_attempt_without_municipality_zip_or_phone_area() -> None:
    session = FakeHTTPSession(
        {
            "https://api.cnpja.com/office": FakeResponse(payload={"records": []})
        },
        default_status_code=None,
    )
    provider = CNPJAProvider(
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpja_commercial",
            CNPJA_API_KEY="cnpja-key",
            CNPJA_API_BASE_URL="https://api.cnpja.com",
            CNPJA_NAME_VARIANT_LIMIT=4,
            CNPJA_MAX_SEARCH_ATTEMPTS_PER_LEAD=2,
        ),
        http_session=session,
    )

    results = provider.search_companies(
        business_name="Pet Shop Bela Vista | Banho Carinhoso",
        state="SP",
    )

    assert results == []
    assert len(session.get_calls) == 1
    assert session.get_calls[0][1]["params"]["alias.in"] == "Pet Shop Bela Vista,Bela Vista,Banho Carinhoso"


def test_cnpja_commercial_search_skips_municipality_when_city_mapping_is_missing() -> None:
    session = FakeHTTPSession(
        {
            "https://api.cnpja.com/office": FakeResponse(payload={"records": []})
        },
        default_status_code=None,
    )
    provider = CNPJAProvider(
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpja_commercial",
            CNPJA_API_KEY="cnpja-key",
            CNPJA_API_BASE_URL="https://api.cnpja.com",
        ),
        http_session=session,
    )

    results = provider.search_companies(
        business_name="Loja Exemplo",
        city="Cidade Inventada",
        state="SP",
    )

    assert results == []
    assert "address.municipality.in" not in session.get_calls[0][1]["params"]
    assert provider.last_company_search_metadata is not None
    assert provider.last_company_search_metadata["searched_city"] == "Cidade Inventada"
    assert provider.last_company_search_metadata["searched_municipality_code"] is None
    assert provider.last_company_search_metadata["municipality_mapping_found"] is False


def test_cnpja_commercial_search_uses_londrina_municipality_and_extracts_zip_from_address() -> None:
    session = FakeHTTPSession(
        {
            "https://api.cnpja.com/office": FakeResponse(payload={"records": []})
        },
        default_status_code=None,
    )
    provider = CNPJAProvider(
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpja_commercial",
            CNPJA_API_KEY="cnpja-key",
            CNPJA_API_BASE_URL="https://api.cnpja.com",
        ),
        http_session=session,
    )

    results = provider.search_companies(
        business_name="Empório dos Animais Pet Shop - Av. Higienópolis",
        city="Londrina",
        state="PR",
        postal_code=None,
        address="Av. Higienópolis, 2657 - Guanabara - 86050-000",
        neighborhood="Guanabara",
        phone="(43) 3322-0000",
    )

    assert results == []
    params = session.get_calls[0][1]["params"]
    assert params["address.municipality.in"] == "4113700"
    assert "address.zip.in" not in params
    assert provider.last_company_search_metadata is not None
    assert provider.last_company_search_metadata["searched_city"] == "Londrina"
    assert provider.last_company_search_metadata["searched_municipality_code"] == "4113700"
    assert provider.last_company_search_metadata["searched_zip"] == "86050000"
    assert provider.last_company_search_metadata["extracted_zip_from_address"] is True


def test_cnpja_commercial_search_uses_second_controlled_attempt_after_zero_candidates() -> None:
    session = FakeHTTPSession(
        {
            "https://api.cnpja.com/office": FakeResponse(payload={"records": []})
        },
        default_status_code=None,
    )
    provider = CNPJAProvider(
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpja_commercial",
            CNPJA_API_KEY="cnpja-key",
            CNPJA_API_BASE_URL="https://api.cnpja.com",
            CNPJA_MAX_SEARCH_ATTEMPTS_PER_LEAD=2,
            CNPJA_NAME_VARIANT_LIMIT=4,
        ),
        http_session=session,
    )

    results = provider.search_companies(
        business_name="Cobasi Londrina Centro",
        city="Londrina",
        state="PR",
        phone="(43) 3333-4444",
    )

    assert results == []
    assert len(session.get_calls) == 2
    assert session.get_calls[0][1]["params"]["alias.in"] == "Cobasi,Cobasi Londrina,Cobasi Centro"
    assert session.get_calls[1][1]["params"]["names.in"] == (
        "Cobasi Londrina Centro,Cobasi Londrina,Cobasi,Cobasi Centro"
    )
    assert session.get_calls[1][1]["params"]["phones.area.in"] == "43"
    assert provider.last_company_search_metadata is not None
    assert provider.last_company_search_metadata["search_attempts_count"] == 2
    assert provider.last_company_search_metadata["candidates_returned_count"] == 0


def test_cnpja_commercial_search_skips_second_attempt_when_query_would_be_too_broad() -> None:
    session = FakeHTTPSession(
        {
            "https://api.cnpja.com/office": FakeResponse(payload={"records": []})
        },
        default_status_code=None,
    )
    provider = CNPJAProvider(
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpja_commercial",
            CNPJA_API_KEY="cnpja-key",
            CNPJA_API_BASE_URL="https://api.cnpja.com",
            CNPJA_MAX_SEARCH_ATTEMPTS_PER_LEAD=2,
        ),
        http_session=session,
    )

    results = provider.search_companies(
        business_name="Loja Exemplo",
        city=None,
        state=None,
        postal_code=None,
        phone=None,
        neighborhood=None,
    )

    assert results == []
    assert len(session.get_calls) == 1


def test_cnpja_commercial_search_uses_company_name_for_legal_like_names() -> None:
    session = FakeHTTPSession(
        {
            "https://api.cnpja.com/office": FakeResponse(payload={"records": []})
        },
        default_status_code=None,
    )
    provider = CNPJAProvider(
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpja_commercial",
            CNPJA_API_KEY="cnpja-key",
            CNPJA_API_BASE_URL="https://api.cnpja.com",
            CNPJA_MAX_SEARCH_ATTEMPTS_PER_LEAD=3,
            CNPJA_ENABLE_LEGAL_NAME_ATTEMPT=True,
        ),
        http_session=session,
    )

    provider.search_companies(
        business_name="Tecnocell Comercio e Servicos LTDA",
        city="Guarulhos",
        state="SP",
    )

    assert any("company.name.in" in call[1]["params"] for call in session.get_calls)


def test_cnpja_commercial_legal_name_attempt_is_disabled_by_default() -> None:
    session = FakeHTTPSession(
        {
            "https://api.cnpja.com/office": FakeResponse(payload={"records": []})
        },
        default_status_code=None,
    )
    provider = CNPJAProvider(
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpja_commercial",
            CNPJA_API_KEY="cnpja-key",
            CNPJA_API_BASE_URL="https://api.cnpja.com",
            CNPJA_MAX_SEARCH_ATTEMPTS_PER_LEAD=3,
        ),
        http_session=session,
    )

    provider.search_companies(
        business_name="Tecnocell Comercio e Servicos LTDA",
        city="Guarulhos",
        state="SP",
    )

    assert all("company.name.in" not in call[1]["params"] for call in session.get_calls)


def test_cnpja_commercial_strict_attempt_can_send_zip_and_district() -> None:
    session = FakeHTTPSession(
        {
            "https://api.cnpja.com/office": FakeResponse(payload={"records": []})
        },
        default_status_code=None,
    )
    provider = CNPJAProvider(
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpja_commercial",
            CNPJA_API_KEY="cnpja-key",
            CNPJA_API_BASE_URL="https://api.cnpja.com",
            CNPJA_MAX_SEARCH_ATTEMPTS_PER_LEAD=4,
            CNPJA_ENABLE_STRICT_ADDRESS_ATTEMPT=True,
        ),
        http_session=session,
    )

    provider.search_companies(
        business_name="Empório dos Animais Pet Shop - Av. Higienópolis",
        city="Londrina",
        state="PR",
        address="Av. Higienópolis, 2657 - Guanabara - 86050-000",
        neighborhood="Guanabara",
        phone="(43) 3322-0000",
    )

    assert any("address.zip.in" in call[1]["params"] for call in session.get_calls)
    assert any("address.district.in" in call[1]["params"] for call in session.get_calls)


def test_cnpja_commercial_strict_attempt_is_disabled_by_default() -> None:
    session = FakeHTTPSession(
        {
            "https://api.cnpja.com/office": FakeResponse(payload={"records": []})
        },
        default_status_code=None,
    )
    provider = CNPJAProvider(
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpja_commercial",
            CNPJA_API_KEY="cnpja-key",
            CNPJA_API_BASE_URL="https://api.cnpja.com",
            CNPJA_MAX_SEARCH_ATTEMPTS_PER_LEAD=4,
        ),
        http_session=session,
    )

    provider.search_companies(
        business_name="EmpÃ³rio dos Animais Pet Shop - Av. HigienÃ³polis",
        city="Londrina",
        state="PR",
        address="Av. HigienÃ³polis, 2657 - Guanabara - 86050-000",
        neighborhood="Guanabara",
        phone="(43) 3322-0000",
    )

    assert all("address.zip.in" not in call[1]["params"] for call in session.get_calls)
    assert all("address.district.in" not in call[1]["params"] for call in session.get_calls)


def test_cnpja_commercial_does_not_send_email_domain_filter_by_default() -> None:
    session = FakeHTTPSession(
        {
            "https://api.cnpja.com/office": FakeResponse(payload={"records": []})
        },
        default_status_code=None,
    )
    provider = CNPJAProvider(
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpja_commercial",
            CNPJA_API_KEY="cnpja-key",
            CNPJA_API_BASE_URL="https://api.cnpja.com",
            CNPJA_MAX_SEARCH_ATTEMPTS_PER_LEAD=4,
        ),
        http_session=session,
    )

    provider.search_companies(
        business_name="Tecnocell",
        city="Guarulhos",
        state="SP",
        website="https://tecnocell.com.br",
        address="Rua Beta, 10 - Centro - 07000-000",
    )

    assert all("emails.domain.in" not in call[1]["params"] for call in session.get_calls)


def test_cnpja_commercial_never_sends_social_domain_email_filter() -> None:
    session = FakeHTTPSession(
        {
            "https://api.cnpja.com/office": FakeResponse(payload={"records": []})
        },
        default_status_code=None,
    )
    provider = CNPJAProvider(
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpja_commercial",
            CNPJA_API_KEY="cnpja-key",
            CNPJA_API_BASE_URL="https://api.cnpja.com",
            CNPJA_MAX_SEARCH_ATTEMPTS_PER_LEAD=4,
            CNPJA_USE_EMAIL_DOMAIN_FILTER=True,
        ),
        http_session=session,
    )

    provider.search_companies(
        business_name="Tecnocell",
        city="Guarulhos",
        state="SP",
        website="https://instagram.com/tecnocell",
        address="Rua Beta, 10 - Centro - 07000-000",
    )

    assert all("emails.domain.in" not in call[1]["params"] for call in session.get_calls)


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


def test_cnpja_commercial_search_enabled_but_missing_api_key_returns_safe_reason(db_session) -> None:
    lead = _lead(cnpj=None, website=None)
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    fake_provider = FakeCNPJAProvider()
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpja_commercial",
            CNPJA_API_BASE_URL="https://api.cnpja.com",
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")

    assert fake_provider.search_calls == []
    assert response.summary.company_search_not_configured_count == 1
    assert response.results[0].reason_code == "company_search_not_configured"


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
    assert lead.cnpj_metadata_json["crawl_summary"]["checked_pages_count"] <= 6


def test_cnpj_can_be_found_on_quem_somos_page(db_session) -> None:
    lead = _lead(website="https://quemsomos.example.com", phone=None)
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    http_session = FakeHTTPSession(
        {
            "https://quemsomos.example.com/robots.txt": FakeResponse(
                url="https://quemsomos.example.com/robots.txt",
                text="User-agent: *\nAllow: /\n",
                content_type="text/plain",
            ),
            "https://quemsomos.example.com": FakeResponse(
                url="https://quemsomos.example.com",
                text="<html><body>Bem-vindo</body></html>",
                content_type="text/html; charset=utf-8",
            ),
            "https://quemsomos.example.com/contato": FakeResponse(
                url="https://quemsomos.example.com/contato",
                text="<html><body>Contato</body></html>",
                content_type="text/html; charset=utf-8",
            ),
            "https://quemsomos.example.com/sobre": FakeResponse(
                url="https://quemsomos.example.com/sobre",
                text="<html><body>Sobre</body></html>",
                content_type="text/html; charset=utf-8",
            ),
            "https://quemsomos.example.com/quem-somos": FakeResponse(
                url="https://quemsomos.example.com/quem-somos",
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
    service = CNPJEnrichmentService(db_session, _settings(), provider=fake_provider)  # type: ignore[arg-type]

    response = service.enrich_lead_ids([lead.id], actor="test")

    assert response.summary.matched_count == 1
    assert response.results[0].reason_code == "matched"


def test_cnpj_can_be_found_on_institucional_page(db_session) -> None:
    lead = _lead(website="https://institucional.example.com", phone=None)
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    http_session = FakeHTTPSession(
        {
            "https://institucional.example.com/robots.txt": FakeResponse(
                url="https://institucional.example.com/robots.txt",
                text="User-agent: *\nAllow: /\n",
                content_type="text/plain",
            ),
            "https://institucional.example.com": FakeResponse(
                url="https://institucional.example.com",
                text="<html><body>Início</body></html>",
                content_type="text/html; charset=utf-8",
            ),
            "https://institucional.example.com/contato": FakeResponse(
                url="https://institucional.example.com/contato",
                text="<html><body>Contato</body></html>",
                content_type="text/html; charset=utf-8",
            ),
            "https://institucional.example.com/sobre": FakeResponse(
                url="https://institucional.example.com/sobre",
                text="<html><body>Sobre</body></html>",
                content_type="text/html; charset=utf-8",
            ),
            "https://institucional.example.com/quem-somos": FakeResponse(
                url="https://institucional.example.com/quem-somos",
                text="<html><body>Quem somos</body></html>",
                content_type="text/html; charset=utf-8",
            ),
            "https://institucional.example.com/institucional": FakeResponse(
                url="https://institucional.example.com/institucional",
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
    service = CNPJEnrichmentService(db_session, _settings(), provider=fake_provider)  # type: ignore[arg-type]

    response = service.enrich_lead_ids([lead.id], actor="test")

    assert response.summary.matched_count == 1


def test_cnpj_can_be_found_on_termos_page_via_homepage_link_discovery(db_session) -> None:
    lead = _lead(website="https://termos.example.com", phone=None)
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    http_session = FakeHTTPSession(
        {
            "https://termos.example.com/robots.txt": FakeResponse(
                url="https://termos.example.com/robots.txt",
                text="User-agent: *\nAllow: /\n",
                content_type="text/plain",
            ),
            "https://termos.example.com": FakeResponse(
                url="https://termos.example.com",
                text="<html><body><a href=\"/termos-de-uso\">Termos de uso</a></body></html>",
                content_type="text/html; charset=utf-8",
            ),
            "https://termos.example.com/termos-de-uso": FakeResponse(
                url="https://termos.example.com/termos-de-uso",
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
    service = CNPJEnrichmentService(db_session, _settings(), provider=fake_provider)  # type: ignore[arg-type]

    response = service.enrich_lead_ids([lead.id], actor="test")

    assert response.summary.matched_count == 1
    fetched_urls = [url for url, _ in http_session.get_calls]
    assert "https://termos.example.com/termos-de-uso" in fetched_urls


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
        default_status_code=404,
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(),
        provider=FakeCNPJAProvider(http_session=http_session),  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")

    assert response.summary.website_timeout_count == 1
    assert response.results[0].reason_code == "website_timeout"


def test_homepage_link_discovery_selects_only_high_signal_same_domain_links(db_session) -> None:
    service = EnrichmentService(
        db_session,
        _settings(),
        http_session=FakeHTTPSession(
            {
                "https://discovery.example.com/robots.txt": FakeResponse(
                    url="https://discovery.example.com/robots.txt",
                    text="User-agent: *\nAllow: /\n",
                    content_type="text/plain",
                ),
                "https://discovery.example.com": FakeResponse(
                    url="https://discovery.example.com",
                    text=(
                        "<html><body>"
                        "<a href=\"/quem-somos\">Quem somos</a>"
                        "<a href=\"/legal\">Legal</a>"
                        "<a href=\"/contato\">Contato</a>"
                        "<a href=\"/blog\">Blog</a>"
                        "<a href=\"https://instagram.com/empresa\">Instagram</a>"
                        "<a href=\"mailto:contato@empresa.com\">Email</a>"
                        "<a href=\"tel:+551133334444\">Telefone</a>"
                        "<a href=\"https://externo.example.com/termos\">Externo</a>"
                        "</body></html>"
                    ),
                    content_type="text/html; charset=utf-8",
                ),
                "https://discovery.example.com/quem-somos": FakeResponse(
                    url="https://discovery.example.com/quem-somos",
                    text="<html><body>Quem somos</body></html>",
                    content_type="text/html; charset=utf-8",
                ),
                "https://discovery.example.com/legal": FakeResponse(
                    url="https://discovery.example.com/legal",
                    text="<html><body>Legal</body></html>",
                    content_type="text/html; charset=utf-8",
                ),
                "https://discovery.example.com/contato": FakeResponse(
                    url="https://discovery.example.com/contato",
                    text="<html><body>Contato</body></html>",
                    content_type="text/html; charset=utf-8",
                ),
            },
            default_status_code=404,
        ),
    )

    crawl = service.crawl_public_website_for_cnpj("https://discovery.example.com")
    attempted_urls = [page.url for page in crawl.attempted_pages]

    assert "https://discovery.example.com/quem-somos" in attempted_urls
    assert "https://discovery.example.com/legal" in attempted_urls
    assert "https://discovery.example.com/contato" in attempted_urls
    assert "https://discovery.example.com/blog" not in attempted_urls
    assert "https://externo.example.com/termos" not in attempted_urls
    assert "https://instagram.com/empresa" not in attempted_urls


def test_crawl_stops_after_finding_valid_cnpj_candidate(db_session) -> None:
    lead = _lead(website="https://parada.example.com", phone=None)
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    http_session = FakeHTTPSession(
        {
            "https://parada.example.com/robots.txt": FakeResponse(
                url="https://parada.example.com/robots.txt",
                text="User-agent: *\nAllow: /\n",
                content_type="text/plain",
            ),
            "https://parada.example.com": FakeResponse(
                url="https://parada.example.com",
                text="<html><body>Home</body></html>",
                content_type="text/html; charset=utf-8",
            ),
            "https://parada.example.com/contato": FakeResponse(
                url="https://parada.example.com/contato",
                text="<html><body>CNPJ 37.335.118/0001-80</body></html>",
                content_type="text/html; charset=utf-8",
            ),
            "https://parada.example.com/sobre": FakeResponse(
                url="https://parada.example.com/sobre",
                text="<html><body>Sobre</body></html>",
                content_type="text/html; charset=utf-8",
            ),
        },
        default_status_code=404,
    )
    fake_provider = FakeCNPJAProvider(
        lookup_results_by_cnpj={"37335118000180": _lookup_result(phones=[])},
        http_session=http_session,
    )
    service = CNPJEnrichmentService(db_session, _settings(), provider=fake_provider)  # type: ignore[arg-type]

    response = service.enrich_lead_ids([lead.id], actor="test")
    fetched_urls = [url for url, _ in http_session.get_calls]

    assert response.summary.matched_count == 1
    assert "https://parada.example.com/sobre" not in fetched_urls


def test_crawl_respects_max_page_limit(db_session) -> None:
    session = FakeHTTPSession(
        {
            "https://limite.example.com/robots.txt": FakeResponse(
                url="https://limite.example.com/robots.txt",
                text="User-agent: *\nAllow: /\n",
                content_type="text/plain",
            ),
            "https://limite.example.com": FakeResponse(
                url="https://limite.example.com",
                text=(
                    "<html><body>"
                    "<a href=\"/quem-somos\">Quem somos</a>"
                    "<a href=\"/institucional\">Institucional</a>"
                    "<a href=\"/empresa\">Empresa</a>"
                    "<a href=\"/privacidade\">Privacidade</a>"
                    "<a href=\"/termos\">Termos</a>"
                    "</body></html>"
                ),
                content_type="text/html; charset=utf-8",
            ),
            "https://limite.example.com/contato": FakeResponse(
                url="https://limite.example.com/contato",
                text="<html><body>Contato</body></html>",
                content_type="text/html; charset=utf-8",
            ),
            "https://limite.example.com/sobre": FakeResponse(
                url="https://limite.example.com/sobre",
                text="<html><body>Sobre</body></html>",
                content_type="text/html; charset=utf-8",
            ),
            "https://limite.example.com/quem-somos": FakeResponse(
                url="https://limite.example.com/quem-somos",
                text="<html><body>Quem somos</body></html>",
                content_type="text/html; charset=utf-8",
            ),
            "https://limite.example.com/institucional": FakeResponse(
                url="https://limite.example.com/institucional",
                text="<html><body>Institucional</body></html>",
                content_type="text/html; charset=utf-8",
            ),
            "https://limite.example.com/empresa": FakeResponse(
                url="https://limite.example.com/empresa",
                text="<html><body>Empresa</body></html>",
                content_type="text/html; charset=utf-8",
            ),
            "https://limite.example.com/privacidade": FakeResponse(
                url="https://limite.example.com/privacidade",
                text="<html><body>Privacidade</body></html>",
                content_type="text/html; charset=utf-8",
            ),
            "https://limite.example.com/termos": FakeResponse(
                url="https://limite.example.com/termos",
                text="<html><body>Termos</body></html>",
                content_type="text/html; charset=utf-8",
            ),
        },
        default_status_code=404,
    )
    service = EnrichmentService(db_session, _settings(), http_session=session)

    crawl = service.crawl_public_website_for_cnpj("https://limite.example.com")

    assert crawl.pages_attempted <= 6
    assert crawl.stop_reason in {"page_budget_exhausted", None}


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


def test_cnpj_ws_premium_search_builds_endpoint_and_uses_x_api_token_header() -> None:
    session = FakeHTTPSession(
        {
            "https://comercial.cnpj.ws/v2/pesquisa": FakeResponse(
                payload={
                    "resultados": [
                        {
                            "razao_social": "Casa Falci Ltda",
                            "estabelecimento": {
                                "cnpj": "17247065000139",
                                "nome_fantasia": "Casa Falci",
                                "situacao_cadastral": "Ativa",
                                "cep": "13000-000",
                                "logradouro": "Rua Beta",
                                "numero": "45",
                                "bairro": "Centro",
                                "cidade": {"nome": "Campinas"},
                                "estado": {"sigla": "SP"},
                                "atividade_principal": {"descricao": "Comercio varejista"},
                            },
                        }
                    ]
                }
            )
        },
        default_status_code=None,
    )
    provider = CNPJWSProvider(
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpj_ws_premium",
            CNPJ_WS_PREMIUM_TOKEN="premium-token",
        ),
        http_session=session,
    )

    results = provider.search_companies(
        business_name="Casa Falci",
        city="Campinas",
        state="SP",
        postal_code="13000-000",
    )

    assert session.get_calls[0][0] == "https://comercial.cnpj.ws/v2/pesquisa"
    assert session.get_calls[0][1]["headers"]["x_api_token"] == "premium-token"
    assert "Authorization" not in session.get_calls[0][1]["headers"]
    assert session.get_calls[0][1]["params"]["nome_fantasia"] == "Casa Falci"
    assert session.get_calls[0][1]["params"]["cep"] == "13000000"
    assert session.get_calls[0][1]["params"]["situacao_cadastral"] == "Ativa"
    assert results[0].cnpj == "17247065000139"
    assert results[0].legal_name == "Casa Falci Ltda"
    assert results[0].trade_name == "Casa Falci"
    assert results[0].city == "Campinas"
    assert results[0].state == "SP"
    assert results[0].source_provider == "cnpj_ws_premium"


def test_cnpj_ws_premium_search_can_follow_up_with_direct_lookup_for_cnpj_only_results() -> None:
    session = FakeHTTPSession(
        {
            "https://comercial.cnpj.ws/v2/pesquisa": FakeResponse(
                payload={"resultados": ["17247065000139"]}
            ),
            "https://comercial.cnpj.ws/cnpj/17247065000139": FakeResponse(
                payload={
                    "razao_social": "Casa Falci Ltda",
                    "estabelecimento": {
                        "cnpj": "17247065000139",
                        "nome_fantasia": "Casa Falci",
                        "situacao_cadastral": "Ativa",
                        "cep": "13000-000",
                        "logradouro": "Rua Beta",
                        "numero": "45",
                        "bairro": "Centro",
                        "cidade": {"nome": "Campinas"},
                        "estado": {"sigla": "SP"},
                        "atividade_principal": {"descricao": "Comercio varejista"},
                    },
                }
            ),
        },
        default_status_code=None,
    )
    provider = CNPJWSProvider(
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpj_ws_premium",
            CNPJ_WS_PREMIUM_TOKEN="premium-token",
        ),
        http_session=session,
    )

    results = provider.search_companies(
        business_name="Casa Falci",
        city="Campinas",
        state="SP",
        postal_code="13000-000",
    )

    assert session.get_calls[0][0] == "https://comercial.cnpj.ws/v2/pesquisa"
    assert session.get_calls[1][0] == "https://comercial.cnpj.ws/cnpj/17247065000139"
    assert session.get_calls[1][1]["headers"]["x_api_token"] == "premium-token"
    assert "Authorization" not in session.get_calls[1][1]["headers"]
    assert results[0].cnpj == "17247065000139"
    assert results[0].legal_name == "Casa Falci Ltda"
    assert results[0].source_provider == "cnpj_ws_premium"


def test_cnpjota_provider_builds_search_request_with_preview() -> None:
    session = FakeHTTPSession(
        {
            "https://api.cnpjota.com.br/api/v1/empresas/busca": FakeResponse(
                payload={
                    "data": [
                        {
                            "cnpj": "17247065000139",
                            "razao_social": "Casa Falci Ltda",
                            "nome_fantasia": "Casa Falci",
                            "situacao_cadastral": "Ativa",
                            "cep": "13000-000",
                            "logradouro": "Rua Beta",
                            "numero": "45",
                            "bairro": "Centro",
                            "cidade": "Campinas",
                            "uf": "SP",
                            "telefone": "1133334444",
                            "email": "contato@casafalci.com.br",
                            "atividade_principal": {"descricao": "Comercio varejista"},
                        }
                    ]
                }
            )
        },
        default_status_code=None,
    )
    provider = CNPJotaProvider(
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpjota",
            CNPJOTA_TOKEN="ota-token",
            CNPJOTA_USE_PREVIEW=True,
        ),
        http_session=session,
    )

    results = provider.search_companies(
        business_name="Casa Falci",
        state="SP",
    )

    assert session.get_calls[0][0] == "https://api.cnpjota.com.br/api/v1/empresas/busca"
    assert session.get_calls[0][1]["headers"]["Authorization"] == "Bearer ota-token"
    assert session.get_calls[0][1]["params"]["q"] == "Casa Falci"
    assert session.get_calls[0][1]["params"]["uf"] == "SP"
    assert session.get_calls[0][1]["params"]["limite"] == 10
    assert session.get_calls[0][1]["params"]["preview"] == "true"
    assert results[0].cnpj == "17247065000139"
    assert results[0].legal_name == "Casa Falci Ltda"
    assert results[0].trade_name == "Casa Falci"
    assert results[0].source_provider == "cnpjota"


def test_company_search_is_not_called_when_disabled(db_session) -> None:
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
                text="<html><body>Fale conosco.</body></html>",
                content_type="text/html; charset=utf-8",
            ),
        },
        default_status_code=404,
    )
    fake_provider = FakeCNPJAProvider(
        search_results=[_lookup_result(source_provider="cnpj_ws_premium")],
        http_session=http_session,
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(CNPJ_COMPANY_SEARCH_ENABLED=False),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")

    assert fake_provider.search_calls == []
    assert response.summary.company_search_no_candidates_count == 0
    assert response.results[0].reason_code == "no_cnpj_on_website"


def test_cnpjota_search_enabled_but_token_missing_returns_safe_reason(db_session) -> None:
    lead = _lead(cnpj=None, website=None)
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    fake_provider = FakeCNPJAProvider()
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpjota",
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")

    assert fake_provider.search_calls == []
    assert response.summary.company_search_not_configured_count == 1
    assert response.results[0].reason_code == "company_search_not_configured"


def test_company_search_enabled_but_token_missing_returns_safe_reason(db_session) -> None:
    lead = _lead(cnpj=None, website=None)
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    fake_provider = FakeCNPJAProvider()
    service = CNPJEnrichmentService(
        db_session,
        _settings(CNPJ_COMPANY_SEARCH_ENABLED=True),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")

    assert fake_provider.search_calls == []
    assert response.summary.company_search_not_configured_count == 1
    assert response.results[0].reason_code == "company_search_not_configured"


def test_cnpjota_high_confidence_candidate_fills_cnpj(db_session) -> None:
    lead = _lead(cnpj=None, website=None)
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    fake_provider = FakeCNPJAProvider(
        search_results=[_lookup_result(source_provider="cnpjota")]
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpjota",
            CNPJOTA_TOKEN="ota-token",
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")
    db_session.refresh(lead)

    assert response.summary.matched_count == 1
    assert response.summary.company_search_matched_count == 1
    assert lead.cnpj == "37335118000180"
    assert lead.legal_name == "Oficina CNPJ LTDA"
    assert lead.cnpj_source_provider == "cnpjota"


def test_cnpjota_preview_masked_candidate_does_not_autofill(db_session) -> None:
    lead = _lead(cnpj=None, website=None)
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    preview_candidate = CNPJLookupResult(
        cnpj="17.247.***/*",
        legal_name="Oficina CNPJ LTDA",
        trade_name="Oficina CNPJ",
        registration_status="Ativa",
        address="Rua Alfa, 10",
        city="Campinas",
        state="SP",
        postal_code="13000-000",
        website=None,
        domain=None,
        phones=["1133334444"],
        emails=[],
        primary_activity="Oficina mecanica",
        source_provider="cnpjota",
        provider_record_id="preview-1",
        metadata={
            "queried_via": "cnpjota",
            "preview_mode": True,
            "full_cnpj_available": False,
            "masked_cnpj": "17.247.***/*",
        },
    )
    fake_provider = FakeCNPJAProvider(search_results=[preview_candidate])
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpjota",
            CNPJOTA_TOKEN="ota-token",
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")
    db_session.refresh(lead)

    assert response.summary.needs_review_count == 1
    assert response.summary.company_search_needs_review_count == 1
    assert response.results[0].reason_code == "company_search_preview_only"
    assert lead.cnpj is None
    assert lead.cnpj_match_status == "needs_review"


def test_cnpjota_medium_confidence_candidate_becomes_needs_review(db_session) -> None:
    lead = _lead(cnpj=None, website=None, phone=None, whatsapp=None, postal_code=None)
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    fake_provider = FakeCNPJAProvider(
        search_results=[_lookup_result(source_provider="cnpjota", phones=[], website=None)]
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpjota",
            CNPJOTA_TOKEN="ota-token",
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")

    assert response.summary.needs_review_count == 1
    assert response.results[0].reason_code == "company_search_needs_review"


def test_cnpjota_name_only_candidate_does_not_autofill(db_session) -> None:
    lead = _lead(
        business_name="Loja Exemplo",
        cnpj=None,
        website=None,
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

    fake_provider = FakeCNPJAProvider(
        search_results=[
            _lookup_result(
                source_provider="cnpjota",
                trade_name="Loja Exemplo",
                legal_name="Loja Exemplo Ltda",
                phones=[],
                address=None,
                postal_code=None,
                city=None,
                state=None,
                website=None,
            )
        ]
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpjota",
            CNPJOTA_TOKEN="ota-token",
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")

    assert response.summary.not_found_count == 1
    assert response.summary.company_search_low_confidence_count == 1
    assert response.results[0].reason_code == "company_search_low_confidence"


def test_cnpjota_rate_limit_is_reported_safely(db_session) -> None:
    lead = _lead(cnpj=None, website=None)
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    fake_provider = FakeCNPJAProvider(
        search_error=CNPJAProviderError(
            "CNPJota search hit the upstream usage limit. Retry shortly.",
            status_code=503,
        )
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpjota",
            CNPJOTA_TOKEN="ota-token",
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")

    assert response.summary.company_search_rate_limited_count == 1
    assert response.results[0].reason_code == "company_search_rate_limited"


def test_cnpja_commercial_high_confidence_candidate_fills_cnpj(db_session) -> None:
    lead = _lead(cnpj=None, website=None)
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    fake_provider = FakeCNPJAProvider(
        search_results=[_lookup_result(source_provider="cnpja_commercial")]
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpja_commercial",
            CNPJA_API_KEY="cnpja-key",
            CNPJA_API_BASE_URL="https://api.cnpja.com",
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")
    db_session.refresh(lead)

    assert response.summary.matched_count == 1
    assert response.summary.company_search_matched_count == 1
    assert response.results[0].reason_code == "company_search_matched"
    assert lead.cnpj == "37335118000180"
    assert lead.legal_name == "Oficina CNPJ LTDA"
    assert lead.cnpj_source_provider == "cnpja_commercial"


def test_cnpja_commercial_medium_confidence_candidate_needs_review(db_session) -> None:
    lead = _lead(cnpj=None, website=None, phone=None, whatsapp=None, postal_code=None)
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    fake_provider = FakeCNPJAProvider(
        search_results=[
            _lookup_result(
                source_provider="cnpja_commercial",
                phones=[],
                website=None,
                metadata_extra={
                    "company_search_query_mode": "alias",
                    "company_search_query_mode_label": "Nome fantasia",
                },
            )
        ]
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpja_commercial",
            CNPJA_API_KEY="cnpja-key",
            CNPJA_API_BASE_URL="https://api.cnpja.com",
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")
    db_session.refresh(lead)

    assert response.summary.needs_review_count == 1
    assert response.summary.company_search_needs_review_count == 1
    assert response.results[0].reason_code == "company_search_needs_review"
    assert lead.cnpj is None
    assert lead.cnpj_match_status == "needs_review"
    assert lead.cnpj_metadata_json["candidate_summary"]["cnpj"] == "37335118000180"
    assert lead.cnpj_metadata_json["candidate_summary"]["provider"] == "cnpja_commercial"
    assert lead.cnpj_metadata_json["candidate_summary"]["query_mode_label"] == "Nome fantasia"
    assert lead.cnpj_metadata_json["candidate_summary"]["evidence"]["alias_name"] == 25
    assert lead.cnpj_metadata_json["candidate_summary"]["evidence"]["activity"] == 5
    assert lead.cnpj_metadata_json["crawl_summary"]["company_search"]["top_candidate_score"] == 70
    assert (
        lead.cnpj_metadata_json["crawl_summary"]["company_search"]["top_candidate_rejection_reason"]
        == "below_autofill_threshold"
    )


def test_cnpja_commercial_alias_match_can_confirm_person_like_legal_name(db_session) -> None:
    lead = _lead(
        business_name="Tecnocell",
        cnpj=None,
        website=None,
        phone="(11) 3333-4444",
        postal_code="07000-000",
        city="Guarulhos",
        state="SP",
    )
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    fake_provider = FakeCNPJAProvider(
        search_results=[
            _lookup_result(
                source_provider="cnpja_commercial",
                legal_name="Lubia Ramdia Rabah",
                trade_name="Tecnocell",
                city="Guarulhos",
                state="SP",
                postal_code="07000-000",
                phones=["1133334444"],
                website=None,
                primary_activity="Assistencia tecnica de celulares",
                metadata_extra={
                    "company_search_query_mode": "alias",
                    "company_search_query_mode_label": "Nome fantasia",
                },
            )
        ]
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpja_commercial",
            CNPJA_API_KEY="cnpja-key",
            CNPJA_API_BASE_URL="https://api.cnpja.com",
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")
    db_session.refresh(lead)

    assert response.summary.matched_count == 1
    assert lead.cnpj == "37335118000180"
    assert lead.cnpj_match_status == "matched"
    assert lead.cnpj_metadata_json["candidate_summary"]["trade_name"] == "Tecnocell"
    assert lead.cnpj_metadata_json["candidate_summary"]["legal_name_note"]


def test_cnpja_commercial_name_only_candidate_does_not_autofill(db_session) -> None:
    lead = _lead(
        business_name="Loja Exemplo",
        cnpj=None,
        website=None,
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

    fake_provider = FakeCNPJAProvider(
        search_results=[
            _lookup_result(
                source_provider="cnpja_commercial",
                trade_name="Loja Exemplo",
                legal_name="Loja Exemplo Ltda",
                phones=[],
                address=None,
                postal_code=None,
                city=None,
                state=None,
                website=None,
            )
        ]
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpja_commercial",
            CNPJA_API_KEY="cnpja-key",
            CNPJA_API_BASE_URL="https://api.cnpja.com",
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")

    assert response.summary.not_found_count == 1
    assert response.summary.company_search_low_confidence_count == 1
    assert response.results[0].reason_code == "company_search_low_confidence"
    assert lead.cnpj_metadata_json["crawl_summary"]["company_search"]["top_candidate_score"] < 60
    assert (
        lead.cnpj_metadata_json["crawl_summary"]["company_search"]["top_candidate_rejection_reason"]
        == "insufficient_identity_support"
    )


def test_cnpja_commercial_different_city_state_does_not_autofill(db_session) -> None:
    lead = _lead(cnpj=None, website=None)
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    fake_provider = FakeCNPJAProvider(
        search_results=[
            _lookup_result(
                source_provider="cnpja_commercial",
                city="Curitiba",
                state="PR",
            )
        ]
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpja_commercial",
            CNPJA_API_KEY="cnpja-key",
            CNPJA_API_BASE_URL="https://api.cnpja.com",
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")
    db_session.refresh(lead)

    assert response.summary.not_found_count == 1
    assert response.summary.company_search_low_confidence_count == 1
    assert lead.cnpj is None


def test_cnpja_zero_candidate_response_is_not_reported_as_provider_error(db_session) -> None:
    lead = _lead(cnpj=None, website=None, business_name="Pet Space do Bixiga")
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    fake_provider = FakeCNPJAProvider(
        search_results=[],
        search_metadata={
            "provider": "cnpja_commercial",
            "cnpja_zero_candidates": True,
            "searched_names": ["Pet Space do Bixiga", "Pet Space", "Bixiga"],
            "searched_state": "SP",
            "searched_district": "Bela Vista",
            "search_attempts_count": 2,
            "candidates_returned_count": 0,
        },
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpja_commercial",
            CNPJA_API_KEY="cnpja-key",
            CNPJA_API_BASE_URL="https://api.cnpja.com",
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")
    db_session.refresh(lead)

    assert response.summary.company_search_no_candidates_count == 1
    assert response.summary.company_search_zero_candidates_count == 1
    assert response.summary.company_search_provider_error_count == 0
    assert response.results[0].reason_code == "cnpja_zero_candidates"
    assert lead.cnpj_metadata_json["crawl_summary"]["company_search"]["searched_names"] == [
        "Pet Space do Bixiga",
        "Pet Space",
        "Bixiga",
    ]
    assert lead.cnpj_metadata_json["crawl_summary"]["company_search"]["search_attempts_count"] == 2
    assert lead.cnpj_metadata_json["crawl_summary"]["company_search"]["candidates_returned_count"] == 0


def test_cnpja_rate_limit_stops_remaining_paid_searches_in_batch(db_session) -> None:
    leads = [_lead(cnpj=None, website=None, business_name=f"Empresa {index}") for index in range(2)]
    db_session.add_all(leads)
    db_session.commit()
    for lead in leads:
        db_session.refresh(lead)

    fake_provider = FakeCNPJAProvider(
        search_results_sequence=[
            CNPJAProviderError(
                "CNPJA request hit the upstream usage limit. Retry shortly.",
                status_code=503,
            ),
        ]
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpja_commercial",
            CNPJA_API_KEY="cnpja-key",
            CNPJA_API_BASE_URL="https://api.cnpja.com",
            CNPJA_STOP_BATCH_ON_RATE_LIMIT=True,
            CNPJA_BATCH_SIZE=8,
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id for lead in leads], actor="test")

    assert len(fake_provider.search_calls) == 1
    assert response.summary.company_search_rate_limited_count == 1
    assert response.summary.company_search_pending_retry_count == 1
    assert response.summary.not_found_count == 0
    assert {result.reason_code for result in response.results} == {
        "company_search_rate_limited",
        "company_search_pending_retry",
    }


def test_cnpja_batch_size_limit_prevents_extra_paid_calls(db_session) -> None:
    leads = [_lead(cnpj=None, website=None, business_name=f"Empresa {index}") for index in range(2)]
    db_session.add_all(leads)
    db_session.commit()
    for lead in leads:
        db_session.refresh(lead)

    fake_provider = FakeCNPJAProvider(
        search_results=[],
        search_metadata={
            "provider": "cnpja_commercial",
            "cnpja_zero_candidates": True,
            "searched_names": ["Empresa 0"],
        },
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpja_commercial",
            CNPJA_API_KEY="cnpja-key",
            CNPJA_API_BASE_URL="https://api.cnpja.com",
            CNPJA_BATCH_SIZE=1,
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id for lead in leads], actor="test")

    assert len(fake_provider.search_calls) == 1
    assert response.summary.company_search_zero_candidates_count == 1
    assert response.summary.company_search_pending_retry_count == 1
    assert response.summary.not_found_count == 1
    assert sorted(result.reason_code for result in response.results) == [
        "cnpja_zero_candidates",
        "company_search_pending_retry",
    ]


def test_same_lead_query_signature_does_not_call_paid_search_twice_within_cooldown(db_session) -> None:
    lead = _lead(cnpj=None, website=None, business_name="Cobasi Londrina Centro", city="Londrina", state="PR")
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    fake_provider = FakeCNPJAProvider(
        search_results=[],
        search_metadata={
            "provider": "cnpja_commercial",
            "cnpja_zero_candidates": True,
            "searched_names": ["Cobasi", "Cobasi Londrina"],
            "candidates_returned_count": 0,
        },
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpja_commercial",
            CNPJA_API_KEY="cnpja-key",
            CNPJA_API_BASE_URL="https://api.cnpja.com",
            CNPJ_PAID_SEARCH_REPEAT_COOLDOWN_HOURS=24,
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    first_response = service.enrich_lead_ids([lead.id], actor="test")
    second_response = service.enrich_lead_ids([lead.id], actor="test")

    assert first_response.results[0].reason_code == "cnpja_zero_candidates"
    assert len(fake_provider.search_calls) == 1
    assert second_response.summary.paid_search_recently_attempted_count == 1
    assert second_response.results[0].reason_code == "paid_search_recently_attempted"


def test_needs_review_lead_with_valid_candidate_is_skipped_before_repeating_paid_search(db_session) -> None:
    lead = _lead(cnpj=None, website=None, phone=None, whatsapp=None, postal_code=None)
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    fake_provider = FakeCNPJAProvider(
        search_results=[
            _lookup_result(
                source_provider="cnpja_commercial",
                phones=[],
                website=None,
                metadata_extra={
                    "company_search_query_mode": "alias",
                    "company_search_query_mode_label": "Nome fantasia",
                },
            )
        ]
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpja_commercial",
            CNPJA_API_KEY="cnpja-key",
            CNPJA_API_BASE_URL="https://api.cnpja.com",
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    first_response = service.enrich_lead_ids([lead.id], actor="test")
    second_response = service.enrich_lead_ids([lead.id], actor="test")
    db_session.refresh(lead)

    assert first_response.results[0].reason_code == "company_search_needs_review"
    assert len(fake_provider.search_calls) == 1
    assert second_response.summary.skipped_review_candidate_count == 1
    assert second_response.results[0].reason_code == "skipped_review_candidate_exists"
    assert lead.cnpj is None
    assert lead.cnpj_match_status == "needs_review"


def test_expired_paid_search_cooldown_allows_new_company_search(db_session) -> None:
    lead = _lead(cnpj=None, website=None, business_name="Cobasi Londrina Centro", city="Londrina", state="PR")
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    fake_provider = FakeCNPJAProvider(
        search_results=[],
        search_metadata={
            "provider": "cnpja_commercial",
            "cnpja_zero_candidates": True,
            "searched_names": ["Cobasi", "Cobasi Londrina"],
            "candidates_returned_count": 0,
        },
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpja_commercial",
            CNPJA_API_KEY="cnpja-key",
            CNPJA_API_BASE_URL="https://api.cnpja.com",
            CNPJ_PAID_SEARCH_REPEAT_COOLDOWN_HOURS=24,
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    service.enrich_lead_ids([lead.id], actor="test")
    db_session.refresh(lead)
    metadata = dict(lead.cnpj_metadata_json or {})
    metadata["cnpj_paid_search_last_attempt_at"] = (utcnow() - timedelta(hours=25)).isoformat()
    lead.cnpj_metadata_json = metadata
    db_session.commit()
    db_session.refresh(lead)

    response = service.enrich_lead_ids([lead.id], actor="test")

    assert len(fake_provider.search_calls) == 2
    assert response.summary.paid_search_recently_attempted_count == 0


def test_company_search_high_confidence_candidate_fills_cnpj(db_session) -> None:
    lead = _lead(cnpj=None, website=None)
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    fake_provider = FakeCNPJAProvider(
        search_results=[_lookup_result(source_provider="cnpj_ws_premium")]
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpj_ws_premium",
            CNPJ_WS_PREMIUM_TOKEN="premium-token",
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")
    db_session.refresh(lead)

    assert response.summary.matched_count == 1
    assert response.summary.company_search_matched_count == 1
    assert response.results[0].reason_code == "company_search_matched"
    assert lead.cnpj == "37335118000180"
    assert lead.legal_name == "Oficina CNPJ LTDA"
    assert lead.cnpj_source_provider == "cnpj_ws_premium"


def test_company_search_medium_confidence_candidate_needs_review(db_session) -> None:
    lead = _lead(cnpj=None, website=None, phone=None, whatsapp=None, postal_code=None)
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    fake_provider = FakeCNPJAProvider(
        search_results=[
            _lookup_result(
                source_provider="cnpj_ws_premium",
                phones=[],
                website=None,
            )
        ]
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpj_ws_premium",
            CNPJ_WS_PREMIUM_TOKEN="premium-token",
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")
    db_session.refresh(lead)

    assert response.summary.needs_review_count == 1
    assert response.summary.company_search_needs_review_count == 1
    assert response.results[0].reason_code == "company_search_needs_review"
    assert lead.cnpj is None
    assert lead.cnpj_match_status == "needs_review"
    candidate_summary = lead.cnpj_metadata_json["candidate_summary"]
    assert candidate_summary["cnpj"] == "37335118000180"
    assert candidate_summary["legal_name"] == "Oficina CNPJ LTDA"
    assert candidate_summary["city"] == "Campinas"
    assert candidate_summary["state"] == "SP"
    assert candidate_summary["provider"] == "cnpj_ws_premium"
    assert candidate_summary["match_confidence"] == 0.7
    assert candidate_summary["blocked_from_autofill_reason"] == "below_autofill_threshold"


def test_company_search_high_confidence_review_keeps_block_reason(db_session) -> None:
    lead = _lead(cnpj=None, website=None)
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    fake_provider = FakeCNPJAProvider(
        search_results=[
            _lookup_result(cnpj="37335118000180", legal_name="Empresa A Ltda", source_provider="cnpja_commercial"),
            _lookup_result(cnpj="17247065000139", legal_name="Empresa B Ltda", source_provider="cnpja_commercial"),
        ]
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpja_commercial",
            CNPJA_API_KEY="cnpja-key",
            CNPJA_API_BASE_URL="https://api.cnpja.com",
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")
    db_session.refresh(lead)

    assert response.summary.needs_review_count == 1
    assert response.results[0].match_status == "needs_review"
    assert response.results[0].match_confidence == 1.0
    assert lead.cnpj is None
    assert lead.cnpj_match_status == "needs_review"
    candidate_summary = lead.cnpj_metadata_json["candidate_summary"]
    assert candidate_summary["blocked_from_autofill_reason"] == "ambiguous_top_candidates"
    assert candidate_summary["review_reason"] == "Mais de um candidato forte foi encontrado."


def test_company_search_high_confidence_review_requires_block_reason(db_session) -> None:
    lead = _lead(cnpj=None, website=None)
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    fake_provider = FakeCNPJAProvider(
        search_results=[
            _lookup_result(cnpj="37335118000180", legal_name="Empresa A Ltda", source_provider="cnpja_commercial"),
            _lookup_result(cnpj="17247065000139", legal_name="Empresa B Ltda", source_provider="cnpja_commercial"),
        ]
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpja_commercial",
            CNPJA_API_KEY="cnpja-key",
            CNPJA_API_BASE_URL="https://api.cnpja.com",
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")
    db_session.refresh(lead)

    assert response.results[0].match_confidence == 1.0
    assert response.results[0].reason_code == "company_search_needs_review"
    assert lead.cnpj_metadata_json["candidate_summary"]["blocked_from_autofill_reason"]


def test_company_search_name_only_candidate_does_not_autofill(db_session) -> None:
    lead = _lead(
        business_name="Loja Exemplo",
        cnpj=None,
        website=None,
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

    fake_provider = FakeCNPJAProvider(
        search_results=[
            _lookup_result(
                source_provider="cnpj_ws_premium",
                trade_name="Loja Exemplo",
                legal_name="Loja Exemplo Ltda",
                phones=[],
                address=None,
                postal_code=None,
                city=None,
                state=None,
                website=None,
            )
        ]
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpj_ws_premium",
            CNPJ_WS_PREMIUM_TOKEN="premium-token",
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")

    assert response.summary.not_found_count == 1
    assert response.summary.company_search_low_confidence_count == 1
    assert response.results[0].reason_code == "company_search_low_confidence"


def test_company_search_different_city_state_does_not_autofill(db_session) -> None:
    lead = _lead(cnpj=None, website=None)
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    fake_provider = FakeCNPJAProvider(
        search_results=[
            _lookup_result(
                source_provider="cnpj_ws_premium",
                city="Curitiba",
                state="PR",
            )
        ]
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpj_ws_premium",
            CNPJ_WS_PREMIUM_TOKEN="premium-token",
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")
    db_session.refresh(lead)

    assert response.summary.not_found_count == 1
    assert response.summary.company_search_low_confidence_count == 1
    assert lead.cnpj is None


def test_company_search_no_candidates_returns_reason(db_session) -> None:
    lead = _lead(cnpj=None, website=None)
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    fake_provider = FakeCNPJAProvider(search_results=[])
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpj_ws_premium",
            CNPJ_WS_PREMIUM_TOKEN="premium-token",
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")

    assert response.summary.company_search_no_candidates_count == 1
    assert response.results[0].reason_code == "company_search_no_candidates"


def test_company_search_rate_limit_is_reported_safely(db_session) -> None:
    lead = _lead(cnpj=None, website=None)
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    fake_provider = FakeCNPJAProvider(
        search_error=CNPJAProviderError(
            "CNPJ.ws Premium search hit the upstream usage limit. Retry shortly.",
            status_code=503,
        )
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpj_ws_premium",
            CNPJ_WS_PREMIUM_TOKEN="premium-token",
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")

    assert response.summary.company_search_rate_limited_count == 1
    assert response.summary.error_count == 1
    assert response.results[0].reason_code == "company_search_rate_limited"


def test_website_extraction_runs_before_paid_company_search(db_session) -> None:
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
                text="<html><body>CNPJ 37.335.118/0001-80</body></html>",
                content_type="text/html; charset=utf-8",
            ),
        },
        default_status_code=404,
    )
    fake_provider = FakeCNPJAProvider(
        lookup_results_by_cnpj={"37335118000180": _lookup_result(phones=[])},
        search_results=[_lookup_result(source_provider="cnpj_ws_premium")],
        http_session=http_session,
    )
    service = CNPJEnrichmentService(
        db_session,
        _settings(
            CNPJ_COMPANY_SEARCH_ENABLED=True,
            CNPJ_COMPANY_SEARCH_PROVIDER="cnpj_ws_premium",
            CNPJ_WS_PREMIUM_TOKEN="premium-token",
        ),
        provider=fake_provider,  # type: ignore[arg-type]
    )

    response = service.enrich_lead_ids([lead.id], actor="test")

    assert response.summary.matched_count == 1
    assert fake_provider.search_calls == []


def test_no_cpf_fields_were_added() -> None:
    assert "cpf" not in Lead.__table__.c
    assert "cpf" not in LeadDetail.model_fields


def test_cnpj_review_copy_uses_proper_portuguese_accents_in_backend_messages() -> None:
    service_file = (REPO_ROOT / "app/services/cnpj_enrichment.py").read_text(encoding="utf-8")

    assert "confirmação automática" in service_file
    assert "modo prévia ou mascarados" in service_file
    for bad in ("confirmaÃ", "automÃ", "prÃ©via", "nÃ£o sÃ£o"):
        assert bad not in service_file


def test_cnpj_review_ui_copy_has_no_mojibake_and_shows_manual_review_labels() -> None:
    panel_file = (REPO_ROOT / "web/components/leads/LeadDetailPanel.tsx").read_text(encoding="utf-8")

    assert "Candidato em revisão" in panel_file
    assert "Confira os dados encontrados antes de confirmar o CNPJ deste lead." in panel_file
    assert "Aprovado manualmente." in panel_file
    assert "O candidato ficou abaixo do limite de confirmação automática." in panel_file
    for bad in ("confirmaÃ", "automÃ", "revisÃ", "RazÃ", "EndereÃ", "nÃ£o"):
        assert bad not in panel_file


def test_cnpj_batch_summary_mentions_candidates_needing_review() -> None:
    batch_actions_file = (REPO_ROOT / "web/components/leads/LeadBatchActions.tsx").read_text(encoding="utf-8")

    assert "candidatos encontrados precisam revisão" in batch_actions_file
