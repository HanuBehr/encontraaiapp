from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from app.config import Settings
from app.services.normalization import (
    format_street_address,
    normalize_brazilian_state,
    normalize_domain,
)


MISSING_CNPJA_API_KEY_BATCH_MESSAGE = "CNPJA_API_KEY must be configured to use batch CNPJ enrichment."
COMPANY_SEARCH_NOT_CONFIGURED_MESSAGE = "CNPJA company search is not configured for lead matching."


class CNPJAProviderError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 503) -> None:
        super().__init__(message)
        self.status_code = status_code


class CNPJANotFoundError(CNPJAProviderError):
    def __init__(self, message: str = "CNPJ not found.") -> None:
        super().__init__(message, status_code=404)


@dataclass(slots=True)
class CNPJLookupResult:
    cnpj: str
    legal_name: str | None
    trade_name: str | None
    registration_status: str | None
    address: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    website: str | None
    domain: str | None
    phones: list[str]
    emails: list[str]
    primary_activity: str | None
    source_provider: str
    provider_record_id: str | None
    metadata: dict[str, Any]


def normalize_cnpj(cnpj: str | None) -> str | None:
    if not cnpj:
        return None
    digits = "".join(character for character in str(cnpj) if character.isdigit())
    if len(digits) != 14:
        return None
    return digits


class CNPJAProvider:
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
        normalized_cnpj = normalize_cnpj(cnpj)
        if normalized_cnpj is None:
            raise CNPJANotFoundError("Invalid CNPJ.")

        if self.settings.cnpja_commercial_configured:
            payload = self._commercial_lookup(normalized_cnpj, strategy=strategy)
            source_provider = "cnpja"
        else:
            payload = self._open_lookup(normalized_cnpj)
            source_provider = "cnpja_open"

        return self._normalize_lookup_payload(
            payload,
            source_provider=source_provider,
            requested_cnpj=normalized_cnpj,
            strategy=strategy,
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
        if not self.settings.cnpja_company_search_configured:
            return []

        search_endpoint = (self.settings.cnpja_search_endpoint or "").strip()
        if not search_endpoint:
            return []

        request_payload = {
            "query": business_name,
            "city": city,
            "state": state,
            "postal_code": postal_code,
            "website": website,
            "domain": normalize_domain(website),
            "phone": phone,
            "whatsapp": whatsapp,
            "address": address,
            "neighborhood": neighborhood,
        }
        request_payload = {
            key: value for key, value in request_payload.items() if value not in {None, ""}
        }

        response = self.http.post(
            search_endpoint,
            headers={
                "Authorization": self.settings.cnpja_api_key or "",
                "Content-Type": "application/json",
            },
            json=request_payload,
            timeout=self.REQUEST_TIMEOUT_SECONDS,
        )
        payload = self._json_value_or_raise(response)

        matches: list[CNPJLookupResult] = []
        for candidate_payload in self._extract_search_candidates(payload):
            try:
                matches.append(
                    self._normalize_lookup_payload(
                        candidate_payload,
                        source_provider="cnpja_search",
                        requested_cnpj="",
                        strategy=None,
                    )
                )
            except CNPJANotFoundError:
                continue
        return matches

    def _commercial_lookup(self, cnpj: str, *, strategy: str | None) -> dict[str, Any]:
        base_url = (self.settings.cnpja_api_base_url or "").rstrip("/")
        if not base_url or not self.settings.cnpja_api_key:
            raise CNPJAProviderError(MISSING_CNPJA_API_KEY_BATCH_MESSAGE, status_code=503)

        params: dict[str, str] = {}
        if strategy:
            params["strategy"] = strategy

        response = self.http.get(
            f"{base_url}/office/{cnpj}",
            headers={"Authorization": self.settings.cnpja_api_key},
            params=params,
            timeout=self.REQUEST_TIMEOUT_SECONDS,
        )
        return self._json_or_raise(response)

    def _open_lookup(self, cnpj: str) -> dict[str, Any]:
        base_url = self.settings.cnpja_open_api_base_url.rstrip("/")
        response = self.http.get(
            f"{base_url}/office/{cnpj}",
            timeout=self.REQUEST_TIMEOUT_SECONDS,
        )
        return self._json_or_raise(response)

    def _json_or_raise(self, response: requests.Response) -> dict[str, Any]:
        payload = self._json_value_or_raise(response)
        if not isinstance(payload, dict):
            raise CNPJAProviderError(
                "CNPJA returned an invalid upstream response. Retry shortly.",
                status_code=502,
            )
        return payload

    def _json_value_or_raise(self, response: requests.Response) -> Any:
        status_code = response.status_code
        if status_code in {400, 404}:
            raise CNPJANotFoundError()
        if status_code == 401:
            raise CNPJAProviderError(MISSING_CNPJA_API_KEY_BATCH_MESSAGE, status_code=503)
        if status_code == 429:
            raise CNPJAProviderError(
                "CNPJA request hit the upstream usage limit. Retry shortly.",
                status_code=503,
            )
        if status_code >= 500:
            raise CNPJAProviderError(
                "CNPJA returned an upstream error. Retry shortly.",
                status_code=503,
            )
        try:
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            raise CNPJAProviderError(
                "CNPJA request failed due to an upstream network error. Retry shortly.",
                status_code=503,
            ) from exc
        except ValueError as exc:
            raise CNPJAProviderError(
                "CNPJA returned an invalid upstream response. Retry shortly.",
                status_code=502,
            ) from exc

    def _extract_search_candidates(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]

        if not isinstance(payload, dict):
            return []

        for key in ("results", "items", "offices", "companies", "data"):
            raw_candidates = payload.get(key)
            if isinstance(raw_candidates, list):
                return [item for item in raw_candidates if isinstance(item, dict)]

        if any(
            key in payload
            for key in ("office", "company", "taxId", "cnpj", "companyName", "legalName")
        ):
            return [payload]
        return []

    def _normalize_lookup_payload(
        self,
        payload: dict[str, Any],
        *,
        source_provider: str,
        requested_cnpj: str,
        strategy: str | None,
    ) -> CNPJLookupResult:
        office = _as_dict(payload.get("office")) or payload
        company = _as_dict(office.get("company")) or _as_dict(payload.get("company")) or {}
        address = _as_dict(office.get("address")) or _as_dict(payload.get("address")) or {}
        status = _as_dict(office.get("status")) or _as_dict(payload.get("status")) or {}
        main_activity = (
            _as_dict(office.get("mainActivity"))
            or _as_dict(payload.get("mainActivity"))
            or _as_dict(company.get("mainActivity"))
            or {}
        )

        normalized_cnpj = normalize_cnpj(
            _first_text(
                office.get("taxId"),
                office.get("cnpj"),
                payload.get("taxId"),
                payload.get("cnpj"),
                requested_cnpj,
            )
        )
        if normalized_cnpj is None:
            raise CNPJANotFoundError("Response did not include a valid CNPJ.")

        legal_name = _first_text(
            company.get("name"),
            payload.get("legalName"),
            payload.get("companyName"),
            office.get("companyName"),
        )
        trade_name = _first_text(
            office.get("alias"),
            payload.get("alias"),
            company.get("alias"),
            payload.get("tradeName"),
        )
        registration_status = _first_text(
            status.get("text"),
            status.get("label"),
            status.get("description"),
            office.get("registrationStatus"),
            payload.get("registrationStatus"),
        )
        city = _first_text(address.get("city"), office.get("city"), payload.get("city"))
        state = normalize_brazilian_state(
            _first_text(address.get("state"), office.get("state"), payload.get("state"))
        )
        postal_code = _first_text(
            address.get("zip"),
            address.get("postalCode"),
            office.get("postalCode"),
            payload.get("postalCode"),
        )
        website = _first_text(
            office.get("website"),
            office.get("url"),
            payload.get("website"),
            payload.get("url"),
            company.get("website"),
        )
        street_name = _first_text(address.get("street"), address.get("details"), office.get("address"))
        street_number = _first_text(address.get("number"), office.get("number"), payload.get("number"))
        formatted_address = format_street_address(street_name, street_number)

        phone_values = _extract_contact_values(office.get("phones")) or _extract_contact_values(payload.get("phones"))
        email_values = _extract_contact_values(office.get("emails")) or _extract_contact_values(payload.get("emails"))
        primary_activity = _first_text(
            main_activity.get("text"),
            main_activity.get("description"),
            main_activity.get("name"),
            office.get("mainActivity"),
            payload.get("mainActivity"),
        )

        metadata = {
            "queried_via": source_provider,
            "strategy": strategy,
            "registration_status": registration_status,
            "trade_name": trade_name,
            "primary_activity": primary_activity,
            "city": city,
            "state": state,
            "postal_code": postal_code,
            "website": website,
            "phones_found": len(phone_values),
            "emails_found": len(email_values),
        }
        if office.get("updated") is not None:
            metadata["office_updated"] = office.get("updated")
        if company.get("updated") is not None:
            metadata["company_updated"] = company.get("updated")

        provider_record_id = _first_text(
            office.get("id"),
            office.get("taxId"),
            payload.get("id"),
            normalized_cnpj,
        )
        return CNPJLookupResult(
            cnpj=normalized_cnpj,
            legal_name=legal_name,
            trade_name=trade_name,
            registration_status=registration_status,
            address=formatted_address,
            city=city,
            state=state,
            postal_code=postal_code,
            website=website,
            domain=normalize_domain(website),
            phones=phone_values,
            emails=email_values,
            primary_activity=primary_activity,
            source_provider=source_provider,
            provider_record_id=provider_record_id,
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


def _extract_contact_values(raw_value: Any) -> list[str]:
    if isinstance(raw_value, str):
        stripped = raw_value.strip()
        return [stripped] if stripped else []

    values: list[str] = []
    if isinstance(raw_value, list):
        for item in raw_value:
            if isinstance(item, str):
                stripped = item.strip()
                if stripped:
                    values.append(stripped)
                continue
            if isinstance(item, dict):
                text_value = _first_text(
                    item.get("full"),
                    item.get("number"),
                    item.get("address"),
                    item.get("value"),
                )
                if text_value:
                    values.append(text_value)
    return values
