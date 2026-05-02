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
        return self._normalize_lookup_payload(payload, requested_cnpj=normalized_cnpj)

    def _json_or_raise(self, response: requests.Response) -> dict[str, Any]:
        status_code = response.status_code
        if status_code in {400, 404}:
            raise CNPJANotFoundError()
        if status_code == 429:
            raise CNPJAProviderError(
                "CNPJ.ws request hit the upstream usage limit. Retry shortly.",
                status_code=503,
            )
        if status_code >= 500:
            raise CNPJAProviderError(
                "CNPJ.ws returned an upstream error. Retry shortly.",
                status_code=503,
            )
        try:
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise CNPJAProviderError(
                "CNPJ.ws request failed due to an upstream network error. Retry shortly.",
                status_code=503,
            ) from exc
        except ValueError as exc:
            raise CNPJAProviderError(
                "CNPJ.ws returned an invalid upstream response. Retry shortly.",
                status_code=502,
            ) from exc

        if not isinstance(payload, dict):
            raise CNPJAProviderError(
                "CNPJ.ws returned an invalid upstream response. Retry shortly.",
                status_code=502,
            )
        return payload

    def _normalize_lookup_payload(
        self,
        payload: dict[str, Any],
        *,
        requested_cnpj: str,
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
            "queried_via": "cnpj_ws",
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
            source_provider="cnpj_ws",
            provider_record_id=normalized_cnpj,
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


def _extract_phone_values(establishment: dict[str, Any]) -> list[str]:
    phones: list[str] = []
    for index in ("1", "2"):
        ddd = _first_text(establishment.get(f"ddd{index}"))
        number = _first_text(establishment.get(f"telefone{index}"))
        if ddd and number:
            phones.append(f"{ddd}{number}")
        elif number:
            phones.append(number)
    return phones


def _extract_email_values(establishment: dict[str, Any]) -> list[str]:
    email = _first_text(establishment.get("email"))
    return [email] if email else []
