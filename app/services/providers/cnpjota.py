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


class CNPJotaProvider:
    SEARCH_REQUEST_TIMEOUT_SECONDS = 20
    DEFAULT_SEARCH_LIMIT = 10

    def __init__(
        self,
        settings: Settings,
        *,
        http_session: requests.Session | None = None,
    ) -> None:
        self.settings = settings
        self.http = http_session or requests.Session()

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
        del city, postal_code, website, phone, whatsapp, address, neighborhood

        if not self.settings.cnpjota_company_search_configured:
            return []

        search_term = _first_text(business_name)
        if not search_term:
            return []

        base_url = self.settings.cnpjota_base_url.rstrip("/")
        response = self.http.get(
            f"{base_url}/empresas/busca",
            headers={"Authorization": f"Bearer {self.settings.cnpjota_token or ''}"},
            params={
                "q": search_term,
                "uf": normalize_brazilian_state(state) or state,
                "limite": self.DEFAULT_SEARCH_LIMIT,
                "preview": str(bool(self.settings.cnpjota_use_preview)).lower(),
            },
            timeout=self.SEARCH_REQUEST_TIMEOUT_SECONDS,
        )
        payload = self._json_or_raise(response)

        results: list[CNPJLookupResult] = []
        for item in self._extract_search_candidates(payload):
            candidate = self._normalize_search_candidate_payload(item)
            if candidate is None:
                continue
            results.append(candidate)
        return results

    def _json_or_raise(self, response: requests.Response) -> dict[str, Any]:
        status_code = response.status_code
        if status_code in {400, 404}:
            raise CNPJANotFoundError()
        if status_code in {401, 403}:
            raise CNPJAProviderError(
                "CNPJota search is not configured for lead matching.",
                status_code=503,
            )
        if status_code == 429:
            raise CNPJAProviderError(
                "CNPJota search hit the upstream usage limit. Retry shortly.",
                status_code=503,
            )
        if status_code >= 500:
            raise CNPJAProviderError(
                "CNPJota returned an upstream error. Retry shortly.",
                status_code=503,
            )
        try:
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise CNPJAProviderError(
                "CNPJota request failed due to an upstream network error. Retry shortly.",
                status_code=503,
            ) from exc
        except ValueError as exc:
            raise CNPJAProviderError(
                "CNPJota returned an invalid upstream response. Retry shortly.",
                status_code=502,
            ) from exc

        if not isinstance(payload, dict):
            raise CNPJAProviderError(
                "CNPJota returned an invalid upstream response. Retry shortly.",
                status_code=502,
            )
        return payload

    def _extract_search_candidates(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        for key in ("data", "items", "results", "empresas"):
            raw_candidates = payload.get(key)
            if isinstance(raw_candidates, list):
                return [item for item in raw_candidates if isinstance(item, dict)]
        return []

    def _normalize_search_candidate_payload(self, payload: dict[str, Any]) -> CNPJLookupResult | None:
        address_payload = _as_dict(
            payload.get("endereco")
            or payload.get("address")
            or payload.get("estabelecimento")
        ) or {}
        city_payload = _as_dict(address_payload.get("cidade")) or _as_dict(payload.get("cidade")) or {}
        state_payload = _as_dict(address_payload.get("estado")) or _as_dict(payload.get("estado")) or {}
        activity_payload = (
            _as_dict(payload.get("atividade_principal"))
            or _as_dict(address_payload.get("atividade_principal"))
            or {}
        )

        raw_cnpj = _first_text(
            payload.get("cnpj"),
            payload.get("cnpj_formatado"),
            payload.get("cnpj_mascarado"),
            address_payload.get("cnpj"),
        )
        normalized_cnpj = normalize_cnpj(raw_cnpj)
        full_cnpj_available = normalized_cnpj is not None
        candidate_identifier = normalized_cnpj or raw_cnpj
        if not candidate_identifier:
            return None

        legal_name = _first_text(payload.get("razao_social"), payload.get("legal_name"))
        trade_name = _first_text(payload.get("nome_fantasia"), payload.get("trade_name"))
        registration_status = _status_text(
            payload.get("situacao_cadastral"),
            payload.get("status"),
        )
        postal_code = _first_text(
            address_payload.get("cep"),
            payload.get("cep"),
        )
        city = _first_text(
            city_payload.get("nome"),
            payload.get("cidade_nome"),
            payload.get("cidade"),
            address_payload.get("cidade"),
        )
        state = normalize_brazilian_state(
            _first_text(
                state_payload.get("sigla"),
                payload.get("uf"),
                payload.get("estado"),
                address_payload.get("uf"),
            )
        )
        street = _first_text(
            address_payload.get("logradouro"),
            payload.get("logradouro"),
            address_payload.get("street"),
        )
        number = _first_text(address_payload.get("numero"), payload.get("numero"))
        neighborhood = _first_text(address_payload.get("bairro"), payload.get("bairro"))
        address = format_street_address(street, number)
        website = _first_text(
            payload.get("website"),
            payload.get("site"),
            address_payload.get("website"),
        )
        phones = _extract_phone_values(payload, address_payload)
        emails = _extract_email_values(payload, address_payload)
        primary_activity = _first_text(
            activity_payload.get("descricao"),
            payload.get("cnae_principal_descricao"),
        )

        preview_mode = bool(self.settings.cnpjota_use_preview)
        metadata = {
            "queried_via": "cnpjota",
            "trade_name": trade_name,
            "registration_status": registration_status,
            "primary_activity": primary_activity,
            "city": city,
            "state": state,
            "postal_code": postal_code,
            "neighborhood": neighborhood,
            "website": website,
            "phones_found": len(phones),
            "emails_found": len(emails),
            "preview_mode": preview_mode,
            "full_cnpj_available": full_cnpj_available,
            "masked_cnpj": None if full_cnpj_available else raw_cnpj,
            "search_candidate": True,
        }

        return CNPJLookupResult(
            cnpj=candidate_identifier,
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
            source_provider="cnpjota",
            provider_record_id=_first_text(payload.get("id"), candidate_identifier),
            metadata=metadata,
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


def _status_text(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
        if isinstance(value, dict):
            text = _first_text(
                value.get("descricao"),
                value.get("description"),
                value.get("status"),
                value.get("texto"),
                value.get("nome"),
            )
            if text:
                return text
    return None


def _extract_phone_values(*sources: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for source in sources:
        for key in ("telefone", "telefone1", "telefone2", "celular", "whatsapp"):
            raw_value = _first_text(source.get(key))
            if raw_value:
                values.append(raw_value)
        for key in ("telefones", "phones"):
            raw_value = source.get(key)
            if isinstance(raw_value, list):
                for item in raw_value:
                    if isinstance(item, str):
                        stripped = item.strip()
                        if stripped:
                            values.append(stripped)
                    elif isinstance(item, dict):
                        phone_value = _first_text(
                            item.get("numero"),
                            item.get("telefone"),
                            item.get("value"),
                        )
                        if phone_value:
                            values.append(phone_value)
    return list(dict.fromkeys(values))


def _extract_email_values(*sources: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for source in sources:
        for key in ("email",):
            email = _first_text(source.get(key))
            if email:
                values.append(email)
        for key in ("emails",):
            raw_value = source.get(key)
            if isinstance(raw_value, list):
                for item in raw_value:
                    if isinstance(item, str):
                        stripped = item.strip()
                        if stripped:
                            values.append(stripped)
                    elif isinstance(item, dict):
                        email = _first_text(item.get("email"), item.get("value"))
                        if email:
                            values.append(email)
    return list(dict.fromkeys(values))
