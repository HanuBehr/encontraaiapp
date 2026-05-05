from __future__ import annotations

from typing import Any

import requests

from app.config import Settings
from app.services.normalization import (
    format_street_address,
    normalize_brazilian_state,
    normalize_domain,
)
from app.services.providers.cnpja import (
    CNPJAProviderError,
    CNPJANotFoundError,
    CNPJLookupResult,
    normalize_cnpj,
)


class CNPJWSProvider:
    REQUEST_TIMEOUT_SECONDS = 20
    SEARCH_REQUEST_TIMEOUT_SECONDS = 20
    COMMERCIAL_LOOKUP_REQUEST_TIMEOUT_SECONDS = 20
    DEFAULT_SEARCH_LIMIT = 10
    MAX_FOLLOWUP_LOOKUPS = 5
    MIN_SEARCH_TERM_LENGTH = 3

    def __init__(
        self,
        settings: Settings,
        *,
        http_session: requests.Session | None = None,
    ) -> None:
        self.settings = settings
        self.http = http_session or requests.Session()

    def lookup_known_cnpj(
        self,
        cnpj: str,
        strategy: str | None = None,
    ) -> CNPJLookupResult:
        del strategy

        normalized_cnpj = normalize_cnpj(cnpj)
        if normalized_cnpj is None:
            raise CNPJANotFoundError("Invalid CNPJ.")

        base_url = self.settings.cnpj_ws_base_url.rstrip("/")
        response = self.http.get(
            f"{base_url}/cnpj/{normalized_cnpj}",
            timeout=self.REQUEST_TIMEOUT_SECONDS,
        )
        payload = self._json_or_raise(response)
        return self._normalize_lookup_payload(
            payload,
            requested_cnpj=normalized_cnpj,
            source_provider="cnpj_ws",
            queried_via="cnpj_ws",
        )

    def lookup_commercial_cnpj(self, cnpj: str) -> CNPJLookupResult:
        normalized_cnpj = normalize_cnpj(cnpj)
        if normalized_cnpj is None:
            raise CNPJANotFoundError("Invalid CNPJ.")

        base_url = self.settings.cnpj_ws_premium_base_url.rstrip("/")
        response = self.http.get(
            f"{base_url}/cnpj/{normalized_cnpj}",
            headers=self._commercial_headers(),
            timeout=self.COMMERCIAL_LOOKUP_REQUEST_TIMEOUT_SECONDS,
        )
        payload = self._json_or_raise(
            response,
            provider_label="CNPJ.ws Premium commercial lookup",
            rate_limit_message="CNPJ.ws Premium search hit the upstream usage limit. Retry shortly.",
            auth_missing_message="CNPJ.ws Premium search is not configured for lead matching.",
        )
        return self._normalize_lookup_payload(
            payload,
            requested_cnpj=normalized_cnpj,
            source_provider="cnpj_ws_premium",
            queried_via="cnpj_ws_premium_lookup",
        )

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
        del city, state, website, phone, whatsapp, address, neighborhood

        if not self.settings.cnpj_ws_premium_company_search_configured:
            return []

        search_term = _first_text(business_name)
        if not search_term or len(search_term.strip()) < self.MIN_SEARCH_TERM_LENGTH:
            return []

        base_url = self.settings.cnpj_ws_premium_base_url.rstrip("/")
        query_variants = self._build_search_query_variants(search_term)
        params_base: dict[str, Any] = {
            "limite": self.DEFAULT_SEARCH_LIMIT,
            "situacao_cadastral": "Ativa",
        }
        normalized_postal_code = _normalize_postal_code(postal_code)
        if normalized_postal_code:
            params_base["cep"] = normalized_postal_code

        matches_by_cnpj: dict[str, CNPJLookupResult] = {}
        followup_lookups = 0
        for query_variant in query_variants:
            params = {**params_base, **query_variant}
            response = self.http.get(
                f"{base_url}/v2/pesquisa",
                headers=self._commercial_headers(),
                params=params,
                timeout=self.SEARCH_REQUEST_TIMEOUT_SECONDS,
            )
            payload = self._json_or_raise(
                response,
                provider_label="CNPJ.ws Premium search",
                rate_limit_message="CNPJ.ws Premium search hit the upstream usage limit. Retry shortly.",
                auth_missing_message="CNPJ.ws Premium search is not configured for lead matching.",
            )

            for raw_candidate in self._extract_search_candidates(payload):
                followup_budget = self.MAX_FOLLOWUP_LOOKUPS - followup_lookups
                try:
                    result, followup_used = self._resolve_search_candidate(
                        raw_candidate,
                        followup_budget=followup_budget,
                    )
                except CNPJANotFoundError:
                    continue
                if result is None:
                    continue
                followup_lookups += followup_used
                matches_by_cnpj.setdefault(result.cnpj, result)

            if matches_by_cnpj:
                break

        return list(matches_by_cnpj.values())

    def _commercial_headers(self) -> dict[str, str]:
        token = (self.settings.cnpj_ws_premium_token or "").strip()
        if self.settings.cnpj_ws_premium_auth_mode == "authorization_bearer":
            return {"Authorization": f"Bearer {token}"}
        return {"x_api_token": token}

    def _resolve_search_candidate(
        self,
        raw_candidate: dict[str, Any] | str,
        *,
        followup_budget: int,
    ) -> tuple[CNPJLookupResult | None, int]:
        if isinstance(raw_candidate, str):
            normalized_cnpj = normalize_cnpj(raw_candidate)
            if normalized_cnpj is None or followup_budget <= 0:
                return None, 0
            return self.lookup_commercial_cnpj(normalized_cnpj), 1

        if not isinstance(raw_candidate, dict):
            return None, 0

        if self._search_candidate_has_details(raw_candidate):
            return self._normalize_search_candidate_payload(raw_candidate), 0

        normalized_cnpj = self._extract_search_candidate_cnpj(raw_candidate)
        if normalized_cnpj is None or followup_budget <= 0:
            return None, 0
        return self.lookup_commercial_cnpj(normalized_cnpj), 1

    def _json_or_raise(
        self,
        response: requests.Response,
        *,
        provider_label: str = "CNPJ.ws",
        rate_limit_message: str = "CNPJ.ws request hit the upstream usage limit. Retry shortly.",
        auth_missing_message: str | None = None,
    ) -> dict[str, Any]:
        status_code = response.status_code
        if status_code in {400, 404}:
            raise CNPJANotFoundError()
        if status_code in {401, 403} and auth_missing_message:
            raise CNPJAProviderError(auth_missing_message, status_code=503)
        if status_code == 429:
            raise CNPJAProviderError(rate_limit_message, status_code=503)
        if status_code >= 500:
            raise CNPJAProviderError(
                f"{provider_label} returned an upstream error. Retry shortly.",
                status_code=503,
            )
        try:
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise CNPJAProviderError(
                f"{provider_label} request failed due to an upstream network error. Retry shortly.",
                status_code=503,
            ) from exc
        except ValueError as exc:
            raise CNPJAProviderError(
                f"{provider_label} returned an invalid upstream response. Retry shortly.",
                status_code=502,
            ) from exc

        if not isinstance(payload, dict):
            raise CNPJAProviderError(
                f"{provider_label} returned an invalid upstream response. Retry shortly.",
                status_code=502,
            )
        return payload

    def _normalize_lookup_payload(
        self,
        payload: dict[str, Any],
        *,
        requested_cnpj: str,
        source_provider: str,
        queried_via: str,
    ) -> CNPJLookupResult:
        establishment = _as_dict(payload.get("estabelecimento")) or {}
        city_payload = _as_dict(establishment.get("cidade")) or {}
        state_payload = _as_dict(establishment.get("estado")) or {}
        activity_payload = _as_dict(establishment.get("atividade_principal")) or {}

        normalized_cnpj = normalize_cnpj(
            _first_text(
                establishment.get("cnpj"),
                payload.get("cnpj"),
                requested_cnpj,
            )
        )
        if normalized_cnpj is None:
            raise CNPJANotFoundError("Response did not include a valid CNPJ.")

        legal_name = _first_text(
            payload.get("razao_social"),
            establishment.get("razao_social"),
        )
        trade_name = _first_text(establishment.get("nome_fantasia"))
        registration_status = _first_text(
            establishment.get("situacao_cadastral"),
            establishment.get("status"),
        )
        postal_code = _first_text(establishment.get("cep"))
        city = _first_text(city_payload.get("nome"), establishment.get("cidade"))
        state = normalize_brazilian_state(
            _first_text(state_payload.get("sigla"), establishment.get("estado"))
        )
        address = format_street_address(
            _first_text(establishment.get("logradouro")),
            _first_text(establishment.get("numero")),
        )
        phones = _extract_phone_values(establishment)
        emails = _extract_email_values(establishment)
        primary_activity = _first_text(activity_payload.get("descricao"))
        website = _first_text(
            establishment.get("website"),
            establishment.get("site"),
        )

        metadata = {
            "queried_via": queried_via,
            "trade_name": trade_name,
            "registration_status": registration_status,
            "primary_activity": primary_activity,
            "city": city,
            "state": state,
            "postal_code": postal_code,
            "neighborhood": _first_text(establishment.get("bairro")),
            "website": website,
            "phones_found": len(phones),
            "emails_found": len(emails),
        }

        return CNPJLookupResult(
            cnpj=normalized_cnpj,
            legal_name=legal_name,
            trade_name=trade_name,
            registration_status=registration_status,
            address=address,
            city=city,
            state=state,
            postal_code=postal_code,
            website=website,
            domain=normalize_domain(website),
            phones=phones,
            emails=emails,
            primary_activity=primary_activity,
            source_provider=source_provider,
            provider_record_id=normalized_cnpj,
            metadata=metadata,
        )

    def _extract_search_candidates(self, payload: dict[str, Any]) -> list[dict[str, Any] | str]:
        for key in ("resultados", "results", "items", "data"):
            raw_candidates = payload.get(key)
            if isinstance(raw_candidates, list):
                return [item for item in raw_candidates if isinstance(item, (dict, str))]
        return []

    def _normalize_search_candidate_payload(self, payload: dict[str, Any]) -> CNPJLookupResult:
        establishment = _as_dict(payload.get("estabelecimento")) or {}
        city_payload = _as_dict(establishment.get("cidade")) or _as_dict(payload.get("cidade")) or {}
        state_payload = _as_dict(establishment.get("estado")) or _as_dict(payload.get("estado")) or {}
        activity_payload = (
            _as_dict(establishment.get("atividade_principal"))
            or _as_dict(payload.get("atividade_principal"))
            or {}
        )

        normalized_cnpj = normalize_cnpj(
            _first_text(
                establishment.get("cnpj"),
                payload.get("cnpj"),
                payload.get("cnpj_completo"),
            )
        )
        if normalized_cnpj is None:
            raise CNPJANotFoundError("Response did not include a valid CNPJ.")

        legal_name = _first_text(payload.get("razao_social"), establishment.get("razao_social"))
        trade_name = _first_text(
            establishment.get("nome_fantasia"),
            payload.get("nome_fantasia"),
        )
        registration_status = _first_text(
            establishment.get("situacao_cadastral"),
            payload.get("situacao_cadastral"),
        )
        postal_code = _first_text(establishment.get("cep"), payload.get("cep"))
        city = _first_text(city_payload.get("nome"), establishment.get("cidade"), payload.get("cidade"))
        state = normalize_brazilian_state(
            _first_text(state_payload.get("sigla"), establishment.get("estado"), payload.get("estado"))
        )
        address = format_street_address(
            _first_text(establishment.get("logradouro"), payload.get("logradouro")),
            _first_text(establishment.get("numero"), payload.get("numero")),
        )
        phones = _extract_phone_values(establishment) or _extract_phone_values(payload)
        emails = _extract_email_values(establishment) or _extract_email_values(payload)
        primary_activity = _first_text(activity_payload.get("descricao"))
        website = _first_text(
            establishment.get("website"),
            establishment.get("site"),
            payload.get("website"),
            payload.get("site"),
        )

        metadata = {
            "queried_via": "cnpj_ws_premium",
            "trade_name": trade_name,
            "registration_status": registration_status,
            "primary_activity": primary_activity,
            "city": city,
            "state": state,
            "postal_code": postal_code,
            "neighborhood": _first_text(establishment.get("bairro"), payload.get("bairro")),
            "website": website,
            "phones_found": len(phones),
            "emails_found": len(emails),
            "search_candidate": True,
        }

        return CNPJLookupResult(
            cnpj=normalized_cnpj,
            legal_name=legal_name,
            trade_name=trade_name,
            registration_status=registration_status,
            address=address,
            city=city,
            state=state,
            postal_code=postal_code,
            website=website,
            domain=normalize_domain(website),
            phones=phones,
            emails=emails,
            primary_activity=primary_activity,
            source_provider="cnpj_ws_premium",
            provider_record_id=normalized_cnpj,
            metadata=metadata,
        )

    @staticmethod
    def _build_search_query_variants(search_term: str) -> list[dict[str, str]]:
        normalized_term = search_term.strip()
        if not normalized_term:
            return []
        return [
            {"nome_fantasia": normalized_term},
            {"razao_social": normalized_term},
        ]

    @staticmethod
    def _extract_search_candidate_cnpj(payload: dict[str, Any]) -> str | None:
        establishment = _as_dict(payload.get("estabelecimento")) or {}
        return normalize_cnpj(
            _first_text(
                establishment.get("cnpj"),
                payload.get("cnpj"),
                payload.get("cnpj_completo"),
                payload.get("id"),
                payload.get("taxId"),
            )
        )

    @staticmethod
    def _search_candidate_has_details(payload: dict[str, Any]) -> bool:
        establishment = _as_dict(payload.get("estabelecimento")) or {}
        return bool(
            establishment
            or _first_text(
                payload.get("razao_social"),
                payload.get("nome_fantasia"),
                payload.get("cep"),
                payload.get("logradouro"),
                payload.get("cidade"),
                payload.get("estado"),
                payload.get("email"),
                payload.get("telefone"),
                payload.get("site"),
                payload.get("website"),
            )
        )


def _as_dict(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _first_text(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
    return None


def _extract_phone_values(establishment: dict[str, Any]) -> list[str]:
    phones: list[str] = []
    for index in ("1", "2"):
        ddd = _first_text(establishment.get(f"ddd{index}"))
        number = _first_text(establishment.get(f"telefone{index}"))
        if ddd and number:
            phones.append(f"{ddd}{number}")
        elif number:
            phones.append(number)
    phone = _first_text(establishment.get("telefone"))
    if phone:
        phones.append(phone)
    return list(dict.fromkeys(phones))


def _extract_email_values(establishment: dict[str, Any]) -> list[str]:
    email = _first_text(establishment.get("email"))
    return [email] if email else []


def _normalize_postal_code(value: str | None) -> str | None:
    if not value:
        return None
    digits = "".join(character for character in value if character.isdigit())
    return digits or None
