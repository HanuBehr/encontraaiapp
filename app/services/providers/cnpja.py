from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

import requests

from app.config import Settings
from app.services.geo.ibge_municipalities import lookup_ibge_municipality_code
from app.services.normalization import (
    format_street_address,
    normalize_brazilian_state,
    normalize_domain,
    normalize_text,
)


MISSING_CNPJA_API_KEY_BATCH_MESSAGE = "CNPJA_API_KEY must be configured to use batch CNPJ enrichment."
COMPANY_SEARCH_NOT_CONFIGURED_MESSAGE = "CNPJA company search is not configured for lead matching."
_NAME_SPLIT_RE = re.compile(r"[|/\-,()]+")
_WHITESPACE_RE = re.compile(r"\s+")
_ZIP_PATTERN = re.compile(r"(?<!\d)(\d{5})-?(\d{3})(?!\d)")
_SEARCH_CONNECTOR_WORDS = {"de", "da", "do", "das", "dos", "e"}
_SEARCH_LIGHT_NOISE_PHRASES = (
    "banho e tosa",
    "banho",
    "tosa",
    "delivery",
    "unidade",
    "ltda",
    "me",
    "eireli",
)
_SEARCH_HEAVY_NOISE_PHRASES = (
    "pet shop",
    "petshop",
    "loja",
    "comercio",
    "comercio varejista",
    "materiais de construcao",
    "oficina",
    "mecanica",
    "auto",
    "autos",
    "centro automotivo",
    "clinica",
    "restaurante",
)
_ADDRESS_PREFIX_TOKENS = {"av", "avenida", "rua", "rod", "rodovia", "estrada", "travessa", "alameda"}
_GENERIC_BRAND_PREFIX_TOKENS = {"agro", "casa", "loja"}
_KNOWN_CHAIN_BRANDS = (
    "cobasi",
    "petz",
    "leroy merlin",
    "madeiramadeira",
    "telhanorte",
    "c c",
    "tok stok",
    "petlove",
)
_COMMON_CITY_PHRASES = (
    "londrina",
    "curitiba",
    "maringa",
    "ponta grossa",
    "cascavel",
    "foz do iguacu",
    "joinville",
    "florianopolis",
    "porto alegre",
    "caxias do sul",
    "sao paulo",
    "campinas",
    "sorocaba",
    "jundiai",
    "santos",
    "sao jose dos campos",
    "mogi das cruzes",
    "guarulhos",
    "osasco",
    "barueri",
    "embu das artes",
    "ribeirao preto",
    "belo horizonte",
    "rio de janeiro",
    "santana de parnaiba",
)


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
    DEFAULT_COMPANY_SEARCH_LIMIT = 10
    MIN_SEARCH_TERM_LENGTH = 3

    def __init__(
        self,
        settings: Settings,
        *,
        http_session: requests.Session | None = None,
    ) -> None:
        self.settings = settings
        self.http = http_session or requests.Session()
        self.last_company_search_metadata: dict[str, Any] | None = None

    def lookup_known_cnpj(
        self,
        cnpj: str,
        strategy: str | None = None,
    ) -> CNPJLookupResult:
        normalized_cnpj = normalize_cnpj(cnpj)
        if normalized_cnpj is None:
            raise CNPJANotFoundError("Invalid CNPJ.")

        if self.settings.cnpj_lookup_provider == "cnpj_ws":
            from app.services.providers.cnpj_ws import CNPJWSProvider

            return CNPJWSProvider(
                self.settings,
                http_session=self.http,
            ).lookup_known_cnpj(normalized_cnpj, strategy=strategy)

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
        self.last_company_search_metadata = None
        if (
            self.settings.cnpj_company_search_enabled
            and self.settings.cnpj_company_search_provider == "cnpja_commercial"
        ):
            return self._search_companies_commercial(
                business_name=business_name,
                category=None,
                city=city,
                state=state,
                postal_code=postal_code,
                website=website,
                phone=phone,
                whatsapp=whatsapp,
                address=address,
                neighborhood=neighborhood,
            )

        if (
            self.settings.cnpj_company_search_enabled
            and self.settings.cnpj_company_search_provider == "cnpj_ws_premium"
        ):
            from app.services.providers.cnpj_ws import CNPJWSProvider

            return CNPJWSProvider(
                self.settings,
                http_session=self.http,
            ).search_companies(
                business_name=business_name,
                city=city,
                state=state,
                postal_code=postal_code,
                website=website,
                phone=phone,
                whatsapp=whatsapp,
                address=address,
                neighborhood=neighborhood,
            )

        if (
            self.settings.cnpj_company_search_enabled
            and self.settings.cnpj_company_search_provider == "cnpjota"
        ):
            from app.services.providers.cnpjota import CNPJotaProvider

            return CNPJotaProvider(
                self.settings,
                http_session=self.http,
            ).search_companies(
                business_name=business_name,
                city=city,
                state=state,
                postal_code=postal_code,
                website=website,
                phone=phone,
                whatsapp=whatsapp,
                address=address,
                neighborhood=neighborhood,
            )

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

    def _search_companies_commercial(
        self,
        *,
        business_name: str,
        category: str | None = None,
        city: str | None = None,
        state: str | None = None,
        postal_code: str | None = None,
        website: str | None = None,
        phone: str | None = None,
        whatsapp: str | None = None,
        address: str | None = None,
        neighborhood: str | None = None,
    ) -> list[CNPJLookupResult]:
        del website

        if not self.settings.cnpja_company_search_configured:
            return []

        search_variants = build_company_search_name_variants(
            business_name,
            category=category,
            max_variants=self.settings.cnpja_name_variant_limit,
        )
        if not search_variants:
            return []

        base_url = (self.settings.cnpja_api_base_url or "").rstrip("/")
        if not base_url or not self.settings.cnpja_api_key:
            return []

        effective_postal_code, extracted_zip_from_address = _resolve_search_postal_code(
            postal_code,
            address,
        )
        normalized_state = normalize_brazilian_state(state)
        municipality_code = lookup_ibge_municipality_code(city, normalized_state)
        phone_area = _extract_area_code(phone) or _extract_area_code(whatsapp)
        district = _first_text(neighborhood)
        search_attempts = max(1, min(self.settings.cnpja_max_search_attempts_per_lead, 2))
        names_clauses = self._build_commercial_search_name_clauses(
            search_variants,
            municipality_code=municipality_code,
            postal_code=effective_postal_code,
            phone_area=phone_area,
            max_attempts=search_attempts,
        )
        if not names_clauses:
            return []

        search_attempt_metadata: list[dict[str, Any]] = []
        matches: list[CNPJLookupResult] = []
        shared_metadata = self._build_commercial_search_shared_metadata(
            search_variants=search_variants,
            city=city,
            state=normalized_state,
            postal_code=effective_postal_code,
            phone=phone,
            whatsapp=whatsapp,
            neighborhood=neighborhood,
            municipality_code=municipality_code,
            extracted_zip_from_address=extracted_zip_from_address,
        )

        for names_clause in names_clauses:
            params = self._build_commercial_search_params(
                names_in=names_clause,
                city=city,
                state=normalized_state,
                postal_code=effective_postal_code,
                phone=phone,
                whatsapp=whatsapp,
                neighborhood=neighborhood,
            )
            response = self.http.get(
                f"{base_url}/office",
                headers={
                    "Authorization": self.settings.cnpja_api_key,
                    "Accept": "application/json",
                },
                params=params,
                timeout=self.REQUEST_TIMEOUT_SECONDS,
            )
            payload = self._json_value_or_raise(response)
            raw_candidates = self._extract_search_candidates(payload)
            search_attempt_metadata.append(
                {
                    "names_in": names_clause,
                    "candidate_count": len(raw_candidates),
                    "limit": params.get("limit"),
                    "state": params.get("address.state.in"),
                    "municipality_code": params.get("address.municipality.in"),
                    "postal_code": params.get("address.zip.in"),
                    "district": params.get("address.district.in"),
                    "phone_area": params.get("phones.area.in"),
                }
            )

            for candidate_payload in raw_candidates:
                try:
                    matches.append(
                        self._normalize_lookup_payload(
                            candidate_payload,
                            source_provider="cnpja_commercial",
                            requested_cnpj="",
                            strategy=None,
                        )
                    )
                except CNPJANotFoundError:
                    continue

            if matches:
                self.last_company_search_metadata = {
                    **shared_metadata,
                    "search_attempts": search_attempt_metadata,
                    "search_attempts_count": len(search_attempt_metadata),
                    "cnpja_zero_candidates": False,
                    "candidates_returned_count": len(matches),
                    "returned_candidates": len(matches),
                }
                return matches

        self.last_company_search_metadata = {
            **shared_metadata,
            "search_attempts": search_attempt_metadata,
            "search_attempts_count": len(search_attempt_metadata),
            "cnpja_zero_candidates": True,
            "candidates_returned_count": 0,
            "returned_candidates": 0,
        }
        return []

    def _commercial_lookup(self, cnpj: str, *, strategy: str | None) -> dict[str, Any]:
        base_url = (self.settings.cnpja_api_base_url or "").rstrip("/")
        if not base_url or not self.settings.cnpja_api_key:
            raise CNPJAProviderError(MISSING_CNPJA_API_KEY_BATCH_MESSAGE, status_code=503)

        params: dict[str, str] = {}
        effective_strategy = strategy or self.settings.cnpja_search_strategy
        if effective_strategy:
            params["strategy"] = effective_strategy
        if self.settings.cnpja_search_max_age > 0:
            params["maxAge"] = str(self.settings.cnpja_search_max_age)

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

        for key in ("records", "results", "items", "offices", "companies", "data"):
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

    def _build_commercial_search_params(
        self,
        *,
        names_in: str,
        city: str | None,
        state: str | None,
        postal_code: str | None,
        phone: str | None,
        whatsapp: str | None,
        neighborhood: str | None,
    ) -> dict[str, str]:
        params: dict[str, str] = {
            "limit": str(self._normalize_search_limit()),
            "names.in": names_in,
            "status.id.in": "2",
        }

        normalized_state = normalize_brazilian_state(state)
        if normalized_state:
            params["address.state.in"] = normalized_state

        municipality_code = lookup_ibge_municipality_code(city, normalized_state)
        if municipality_code:
            params["address.municipality.in"] = municipality_code

        normalized_postal_code = _normalize_postal_code(postal_code)
        if normalized_postal_code:
            params["address.zip.in"] = normalized_postal_code

        district = _first_text(neighborhood)
        if district:
            params["address.district.in"] = district

        area_code = _extract_area_code(phone) or _extract_area_code(whatsapp)
        if area_code:
            params["phones.area.in"] = area_code

        return params

    def _build_commercial_search_shared_metadata(
        self,
        *,
        search_variants: list[str],
        city: str | None,
        state: str | None,
        postal_code: str | None,
        phone: str | None,
        whatsapp: str | None,
        neighborhood: str | None,
        municipality_code: str | None = None,
        extracted_zip_from_address: bool = False,
    ) -> dict[str, Any]:
        return {
            "provider": "cnpja_commercial",
            "searched_city": _first_text(city),
            "searched_names": search_variants,
            "searched_state": state,
            "searched_municipality_code": municipality_code,
            "municipality_mapping_found": municipality_code is not None,
            "searched_zip": _normalize_postal_code(postal_code),
            "searched_district": _first_text(neighborhood),
            "searched_phone_area": _extract_area_code(phone) or _extract_area_code(whatsapp),
            "extracted_zip_from_address": extracted_zip_from_address,
        }

    def _build_commercial_search_name_clauses(
        self,
        search_variants: list[str],
        *,
        municipality_code: str | None,
        postal_code: str | None,
        phone_area: str | None,
        max_attempts: int,
    ) -> list[str]:
        if not search_variants:
            return []

        clauses = [",".join(search_variants)]
        if max_attempts < 2:
            return clauses

        if not (municipality_code or postal_code or phone_area):
            return clauses

        fallback_variant = _select_company_search_fallback_variant(search_variants)
        if fallback_variant and fallback_variant not in clauses:
            clauses.append(fallback_variant)
        return clauses[:max_attempts]

    def _normalize_search_limit(self) -> int:
        configured = self.settings.cnpja_company_search_limit
        if configured < 1:
            return 1
        if configured > self.DEFAULT_COMPANY_SEARCH_LIMIT:
            return self.DEFAULT_COMPANY_SEARCH_LIMIT
        return configured


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
                area = _first_text(item.get("area"))
                number = _first_text(item.get("number"))
                if area and number:
                    values.append(f"{area}{number}")
                    continue
                text_value = _first_text(
                    item.get("full"),
                    item.get("address"),
                    item.get("value"),
                    item.get("number"),
                )
                if text_value:
                    values.append(text_value)
    return values


def _normalize_postal_code(value: str | None) -> str | None:
    if not value:
        return None
    digits = "".join(character for character in value if character.isdigit())
    return digits or None


def _resolve_search_postal_code(postal_code: str | None, address: str | None) -> tuple[str | None, bool]:
    normalized_postal_code = _normalize_postal_code(postal_code)
    if normalized_postal_code:
        return normalized_postal_code, False
    extracted_from_address = _extract_postal_code_from_text(address)
    if extracted_from_address:
        return extracted_from_address, True
    return None, False


def _extract_postal_code_from_text(value: str | None) -> str | None:
    if not value:
        return None
    match = _ZIP_PATTERN.search(value)
    if not match:
        return None
    return f"{match.group(1)}{match.group(2)}"


def _extract_area_code(value: str | None) -> str | None:
    if not value:
        return None
    digits = "".join(character for character in value if character.isdigit())
    if len(digits) < 10:
        return None
    if len(digits) == 10:
        return digits[:2]
    return digits[-10:-8]


def build_company_search_name_variants(
    business_name: str,
    category: str | None = None,
    *,
    max_variants: int = 4,
) -> list[str]:
    base_full_variant = _clean_company_search_text(business_name)
    chunk_variants = [
        _clean_company_search_text(chunk)
        for chunk in _NAME_SPLIT_RE.split(business_name)
    ]

    extra_noise_phrases: set[str] = set()
    normalized_category = normalize_text(category)
    if normalized_category:
        extra_noise_phrases.add(normalized_category)

    variants: list[str] = []
    seen: set[str] = set()

    def register(candidate: str | None) -> None:
        if not candidate:
            return
        normalized_candidate = normalize_text(candidate)
        if normalized_candidate is None:
            return
        if _looks_like_address_only_variant(normalized_candidate):
            return
        formatted_candidate = _format_company_search_variant(normalized_candidate)
        if not _is_meaningful_company_search_variant(normalized_candidate):
            return
        if normalized_candidate in seen:
            return
        seen.add(normalized_candidate)
        variants.append(formatted_candidate)

    if base_full_variant:
        register(_strip_address_suffix(base_full_variant))
        register(base_full_variant)
        register(_strip_city_tokens(base_full_variant))
        register(_trim_trailing_location_phrase(base_full_variant))
        register(_extract_trailing_location_variant(base_full_variant))
        register(_drop_generic_prefix_variant(_strip_address_suffix(base_full_variant)))
        for candidate in _extract_known_brand_variants(base_full_variant):
            register(candidate)

    for variant in chunk_variants:
        normalized_variant = normalize_text(variant)
        if normalized_variant is None:
            continue
        register(normalized_variant)
        register(_strip_address_suffix(normalized_variant))
        register(
            _strip_company_search_noise(
                normalized_variant,
                phrases=set(_SEARCH_LIGHT_NOISE_PHRASES) | extra_noise_phrases,
            )
        )
        heavy_noise_preserved = _strip_company_search_noise_preserve_connectors(
            _strip_address_suffix(normalized_variant),
            phrases=set(_SEARCH_HEAVY_NOISE_PHRASES) | extra_noise_phrases,
        )
        register(heavy_noise_preserved)
        register(
            _strip_company_search_noise(
                normalized_variant,
                phrases=set(_SEARCH_LIGHT_NOISE_PHRASES)
                | set(_SEARCH_HEAVY_NOISE_PHRASES)
                | extra_noise_phrases,
            )
        )
        register(_strip_city_tokens(normalized_variant))
        register(_trim_trailing_location_phrase(normalized_variant))
        register(_extract_trailing_location_variant(normalized_variant))
        register(_drop_generic_prefix_variant(_strip_address_suffix(normalized_variant)))
        register(_drop_generic_prefix_variant(heavy_noise_preserved))
        register(
            _drop_connector_words_variant(
                _strip_company_search_noise(
                    _strip_city_tokens(normalized_variant),
                    phrases=set(_SEARCH_HEAVY_NOISE_PHRASES) | extra_noise_phrases,
                )
            )
        )
        register(_extract_last_brand_token_variant(normalized_variant))
        for candidate in _extract_known_brand_variants(normalized_variant):
            register(candidate)

    if max_variants < 1:
        return []
    return variants[:max_variants]


def _clean_company_search_text(value: str | None) -> str | None:
    if not value:
        return None
    collapsed = value.replace("'", "").replace("’", "")
    collapsed = _NAME_SPLIT_RE.sub(" ", collapsed)
    collapsed = _WHITESPACE_RE.sub(" ", collapsed).strip()
    return normalize_text(collapsed)


def _strip_company_search_noise(value: str | None, *, phrases: set[str] | tuple[str, ...]) -> str | None:
    normalized = normalize_text(value)
    if normalized is None:
        return None
    candidate = f" {normalized} "
    removed_phrase = False
    for phrase in phrases:
        normalized_phrase = normalize_text(phrase)
        if normalized_phrase and f" {normalized_phrase} " in candidate:
            candidate = candidate.replace(f" {normalized_phrase} ", " ")
            removed_phrase = True
    if not removed_phrase:
        return normalized
    tokens = [
        token
        for token in candidate.split()
        if token not in _SEARCH_CONNECTOR_WORDS
    ]
    return " ".join(tokens) or None


def _strip_company_search_noise_preserve_connectors(
    value: str | None,
    *,
    phrases: set[str] | tuple[str, ...],
) -> str | None:
    normalized = normalize_text(value)
    if normalized is None:
        return None
    candidate = f" {normalized} "
    removed_phrase = False
    for phrase in phrases:
        normalized_phrase = normalize_text(phrase)
        if normalized_phrase and f" {normalized_phrase} " in candidate:
            candidate = candidate.replace(f" {normalized_phrase} ", " ")
            removed_phrase = True
    if not removed_phrase:
        return normalized
    collapsed = _WHITESPACE_RE.sub(" ", candidate).strip()
    return collapsed or None


def _drop_connector_words_variant(value: str | None) -> str | None:
    normalized = normalize_text(value)
    if normalized is None:
        return None
    tokens = [token for token in normalized.split() if token not in _SEARCH_CONNECTOR_WORDS]
    if len(tokens) < 2:
        return normalized
    return " ".join(tokens)


def _trim_trailing_location_phrase(value: str | None) -> str | None:
    normalized = normalize_text(value)
    if normalized is None:
        return None
    tokens = normalized.split()
    if len(tokens) < 3:
        return normalized
    if tokens[-2] in {"de", "da", "do", "das", "dos"} and len(tokens[-1]) >= 4:
        return " ".join(tokens[:-2]) or None
    return normalized


def _strip_address_suffix(value: str | None) -> str | None:
    normalized = normalize_text(value)
    if normalized is None:
        return None
    tokens = normalized.split()
    for index, token in enumerate(tokens):
        if token in _ADDRESS_PREFIX_TOKENS and index > 0:
            trimmed = " ".join(tokens[:index]).strip()
            return trimmed or normalized
    return normalized


def _extract_trailing_location_variant(value: str | None) -> str | None:
    normalized = normalize_text(value)
    if normalized is None:
        return None
    tokens = normalized.split()
    if len(tokens) < 3:
        return None
    if tokens[-2] in {"de", "da", "do", "das", "dos"} and len(tokens[-1]) >= 4:
        return tokens[-1]
    return None


def _strip_city_tokens(value: str | None) -> str | None:
    normalized = normalize_text(value)
    if normalized is None:
        return None

    result = normalized
    for city_phrase in _COMMON_CITY_PHRASES:
        city_tokens = city_phrase.split()
        tokens = result.split()
        if len(tokens) <= len(city_tokens):
            continue
        if tokens[-len(city_tokens):] == city_tokens:
            result = " ".join(tokens[:-len(city_tokens)]) or result
            break
        if len(tokens) > len(city_tokens) and tokens[-len(city_tokens) - 1 : -1] == city_tokens:
            result = " ".join(tokens[:-len(city_tokens)]) or result
            break
    return result


def _extract_last_brand_token_variant(value: str | None) -> str | None:
    normalized = normalize_text(value)
    if normalized is None:
        return None
    tokens = [token for token in normalized.split() if token not in _SEARCH_CONNECTOR_WORDS]
    if len(tokens) < 2:
        return None
    if tokens[0] not in _GENERIC_BRAND_PREFIX_TOKENS:
        return None
    if tokens[-1] in _ADDRESS_PREFIX_TOKENS:
        return None
    return tokens[-1]


def _drop_generic_prefix_variant(value: str | None) -> str | None:
    normalized = normalize_text(value)
    if normalized is None:
        return None
    tokens = normalized.split()
    if len(tokens) < 2:
        return None
    if tokens[0] not in _GENERIC_BRAND_PREFIX_TOKENS:
        return None
    if len(tokens) <= 3 and tokens[1] in _SEARCH_CONNECTOR_WORDS:
        return None
    remainder = " ".join(tokens[1:]).strip()
    return remainder or None


def _extract_known_brand_variants(value: str | None) -> list[str]:
    normalized = normalize_text(value)
    if normalized is None:
        return []

    variants: list[str] = []
    for brand in _KNOWN_CHAIN_BRANDS:
        brand_tokens = brand.split()
        tokens = normalized.split()
        for index in range(0, len(tokens) - len(brand_tokens) + 1):
            if tokens[index : index + len(brand_tokens)] != brand_tokens:
                continue
            brand_phrase = " ".join(brand_tokens)
            variants.append(brand_phrase)

            suffix_tokens = tokens[index + len(brand_tokens) :]
            cleaned_suffix = [
                token
                for token in suffix_tokens
                if token not in _SEARCH_CONNECTOR_WORDS and token not in _ADDRESS_PREFIX_TOKENS
            ]
            cleaned_suffix = [token for token in cleaned_suffix if token not in _COMMON_CITY_PHRASES]

            if suffix_tokens:
                first_suffix = suffix_tokens[0]
                if first_suffix not in _SEARCH_CONNECTOR_WORDS and first_suffix not in _ADDRESS_PREFIX_TOKENS:
                    variants.append(f"{brand_phrase} {first_suffix}")
                if first_suffix in _COMMON_CITY_PHRASES and len(suffix_tokens) > 1:
                    next_suffix = suffix_tokens[1]
                    if next_suffix not in _SEARCH_CONNECTOR_WORDS and next_suffix not in _ADDRESS_PREFIX_TOKENS:
                        variants.append(f"{brand_phrase} {next_suffix}")
            if cleaned_suffix:
                variants.append(f"{brand_phrase} {cleaned_suffix[0]}")
            break
    return variants


def _looks_like_address_only_variant(value: str | None) -> bool:
    normalized = normalize_text(value)
    if normalized is None:
        return False
    tokens = normalized.split()
    if not tokens:
        return False
    return tokens[0] in _ADDRESS_PREFIX_TOKENS


def _is_meaningful_company_search_variant(value: str | None) -> bool:
    normalized = normalize_text(value)
    if normalized is None or len(normalized) < 3:
        return False
    tokens = [token for token in normalized.split() if token not in _SEARCH_CONNECTOR_WORDS]
    if not tokens:
        return False
    generic_terms = {
        token
        for phrase in (*_SEARCH_LIGHT_NOISE_PHRASES, *_SEARCH_HEAVY_NOISE_PHRASES)
        for token in normalize_text(phrase).split()
    }
    return any(token not in generic_terms for token in tokens)


def _select_company_search_fallback_variant(search_variants: list[str]) -> str | None:
    if len(search_variants) < 2:
        return None
    candidates: list[tuple[str, str, int]] = []
    first_variant = normalize_text(search_variants[0])
    first_token = first_variant.split()[0] if first_variant else None

    for candidate in search_variants[1:]:
        normalized = normalize_text(candidate)
        if normalized is None:
            continue
        token_count = len(normalized.split())
        if 1 <= token_count <= 3 and _is_meaningful_company_search_variant(normalized):
            candidates.append((candidate, normalized, token_count))

    if not candidates:
        return search_variants[1]

    if first_token and first_token not in _GENERIC_BRAND_PREFIX_TOKENS:
        preferred = [
            item
            for item in candidates
            if item[1].split()[0] == first_token and item[2] <= 2
        ]
        if preferred:
            return min(preferred, key=lambda item: (item[2], len(item[1])))[0]

    return min(candidates, key=lambda item: (item[2], len(item[1])))[0]


def _format_company_search_variant(value: str) -> str:
    words: list[str] = []
    for token in value.split():
        if len(token) <= 2 and token not in _SEARCH_CONNECTOR_WORDS:
            words.append(token.upper())
        elif token in _SEARCH_CONNECTOR_WORDS:
            words.append(token)
        else:
            words.append(token.capitalize())
    return " ".join(words)
