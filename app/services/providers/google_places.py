from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import quote

import requests

from app.config import Settings
from app.enums import LeadSourceType
from app.schemas.discovery import DiscoveryLeadCandidate
from app.services.normalization import (
    format_street_address,
    normalize_brazilian_state,
    normalize_business_name,
    normalize_domain,
    normalize_phone_br,
    split_street_and_number,
)
from app.services.providers.discovery_base import DiscoveryProvider, ProviderLeadResult

logger = logging.getLogger(__name__)
MISSING_GOOGLE_API_KEY_MESSAGE = "GOOGLE_API_KEY must be configured to use location-based discovery."


class GooglePlacesProviderError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 503) -> None:
        super().__init__(message)
        self.status_code = status_code


class GooglePlacesProvider(DiscoveryProvider):
    TRANSIENT_RETRY_DELAYS_SECONDS = (0.25, 0.75)
    DETAILS_FIELD_MASK = ",".join(
        [
            "id",
            "websiteUri",
            "googleMapsUri",
        ]
    )
    FIELD_MASK = ",".join(
        [
            "places.id",
            "places.displayName",
            "places.formattedAddress",
            "places.addressComponents",
            "places.location",
            "places.websiteUri",
            "places.googleMapsUri",
            "places.nationalPhoneNumber",
            "places.primaryType",
            "places.primaryTypeDisplayName",
            "nextPageToken",
        ]
    )

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def search(
        self,
        *,
        search_term: str,
        location_label: str,
        latitude: float,
        longitude: float,
        radius_m: int,
        max_results: int,
    ) -> list[ProviderLeadResult]:
        if not self.settings.google_api_key:
            raise GooglePlacesProviderError(MISSING_GOOGLE_API_KEY_MESSAGE, status_code=503)

        request_body = {
            "textQuery": f"{search_term} em {location_label}",
            "languageCode": "pt-BR",
            "regionCode": "BR",
            "locationBias": {
                "circle": {
                    "center": {"latitude": latitude, "longitude": longitude},
                    "radius": float(radius_m),
                }
            },
        }
        remaining_results = max(0, max_results)
        collected_results: list[ProviderLeadResult] = []
        seen_place_ids: set[str] = set()
        next_page_token: str | None = None

        while remaining_results > 0:
            page_size = min(remaining_results, 20)
            payload = self._request_places_json(
                method="POST",
                url=f"{self.settings.google_places_base_url}/places:searchText",
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": self.settings.google_api_key,
                    "X-Goog-FieldMask": self.FIELD_MASK,
                },
                json_body={
                    **request_body,
                    "pageSize": page_size,
                    **({"pageToken": next_page_token} if next_page_token else {}),
                },
                operation=f"searchText '{search_term}' in '{location_label}'",
            )
            places = payload.get("places", [])
            if not isinstance(places, list) or not places:
                break

            added_this_page = 0
            for place in places:
                if not isinstance(place, dict):
                    continue
                place_id = str(place.get("id") or "").strip()
                if place_id and place_id in seen_place_ids:
                    continue
                if place_id:
                    seen_place_ids.add(place_id)
                collected_results.append(self._to_result(place))
                added_this_page += 1
                remaining_results -= 1
                if remaining_results == 0:
                    break

            if remaining_results == 0 or added_this_page == 0:
                break

            next_page_token = payload.get("nextPageToken")
            if not isinstance(next_page_token, str) or not next_page_token.strip():
                break

        return collected_results

    def fetch_place_details(self, place_id: str) -> dict[str, Any]:
        if not self.settings.google_api_key:
            raise GooglePlacesProviderError(MISSING_GOOGLE_API_KEY_MESSAGE, status_code=503)

        encoded_place_id = quote(place_id, safe="")
        payload = self._request_places_json(
            method="GET",
            url=f"{self.settings.google_places_base_url}/places/{encoded_place_id}",
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.settings.google_api_key,
                "X-Goog-FieldMask": self.DETAILS_FIELD_MASK,
            },
            operation=f"placeDetails '{place_id}'",
        )
        return payload

    def _to_result(self, place: dict[str, Any]) -> ProviderLeadResult:
        business_name = ((place.get("displayName") or {}).get("text") or "").strip()
        address_components = place.get("addressComponents") or []
        phone = normalize_phone_br(place.get("nationalPhoneNumber"))
        website = place.get("websiteUri")
        google_maps_url = place.get("googleMapsUri")
        neighborhood = self._extract_component(
            address_components,
            {"sublocality", "sublocality_level_1", "neighborhood"},
        )
        city = self._extract_component(address_components, {"locality", "administrative_area_level_2"})
        state = self._extract_state(address_components)
        postal_code = self._extract_component(address_components, {"postal_code"})
        route = self._extract_component(address_components, {"route"})
        street_number = self._extract_component(address_components, {"street_number"})
        fallback_street, fallback_number = split_street_and_number(
            place.get("formattedAddress"),
            neighborhood=neighborhood,
            city=city,
            state=state,
            postal_code=postal_code,
        )
        address = format_street_address(route or fallback_street, street_number or fallback_number)

        candidate = DiscoveryLeadCandidate(
            business_name=business_name,
            normalized_business_name=normalize_business_name(business_name) or business_name.lower(),
            category=self._extract_category(place),
            address=address,
            neighborhood=neighborhood,
            city=city,
            state=state,
            postal_code=postal_code,
            latitude=((place.get("location") or {}).get("latitude")),
            longitude=((place.get("location") or {}).get("longitude")),
            website=website,
            domain=normalize_domain(website),
            email=None,
            phone=phone,
            whatsapp=phone,
            instagram=None,
            google_maps_url=google_maps_url,
            google_place_id=place.get("id"),
            source_provider="google_places",
            source_url=google_maps_url,
            lead_source_type=LeadSourceType.GOOGLE_PLACES,
        )
        return ProviderLeadResult(
            candidate=candidate,
            raw_payload=place,
            provider_record_id=place.get("id"),
            source_url=google_maps_url,
        )

    @staticmethod
    def _extract_category(place: dict[str, Any]) -> str | None:
        primary_display_name = (place.get("primaryTypeDisplayName") or {}).get("text")
        return primary_display_name or place.get("primaryType")

    @staticmethod
    def _extract_component(
        components: list[dict[str, Any]],
        expected_types: set[str],
    ) -> str | None:
        for component in components:
            component_types = set(component.get("types") or [])
            if component_types.intersection(expected_types):
                return component.get("longText") or component.get("shortText")
        return None

    @staticmethod
    def _extract_state(components: list[dict[str, Any]]) -> str | None:
        for component in components:
            component_types = set(component.get("types") or [])
            if "administrative_area_level_1" in component_types:
                return normalize_brazilian_state(component.get("shortText") or component.get("longText"))
        return None

    def _request_places_json(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        operation: str,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response: requests.Response | None = None
        for attempt_index, retry_delay in enumerate((0.0, *self.TRANSIENT_RETRY_DELAYS_SECONDS), start=1):
            if retry_delay > 0:
                time.sleep(retry_delay)
            try:
                request_kwargs: dict[str, Any] = {
                    "headers": headers,
                    "timeout": 30,
                }
                if json_body is not None:
                    request_kwargs["json"] = json_body
                response = requests.request(method, url, **request_kwargs)
                response.raise_for_status()
                break
            except (requests.exceptions.SSLError, requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
                logger.warning(
                    "Google Places transient request failure during %s (attempt %s/%s): %s: %s",
                    operation,
                    attempt_index,
                    len(self.TRANSIENT_RETRY_DELAYS_SECONDS) + 1,
                    exc.__class__.__name__,
                    exc,
                )
                if attempt_index == len(self.TRANSIENT_RETRY_DELAYS_SECONDS) + 1:
                    raise GooglePlacesProviderError(
                        "Google Places request failed due to an upstream SSL/network error. Retry shortly.",
                        status_code=503,
                    ) from exc
            except requests.exceptions.HTTPError as exc:
                upstream_status = exc.response.status_code if exc.response is not None else None
                logger.warning(
                    "Google Places upstream HTTP failure during %s: status=%s",
                    operation,
                    upstream_status,
                )
                raise GooglePlacesProviderError(
                    f"Google Places request failed with upstream status {upstream_status or 'unknown'}. Retry shortly.",
                    status_code=502,
                ) from exc
            except requests.exceptions.RequestException as exc:
                logger.warning(
                    "Google Places request failure during %s: %s: %s",
                    operation,
                    exc.__class__.__name__,
                    exc,
                )
                raise GooglePlacesProviderError(
                    "Google Places request failed due to an upstream SSL/network error. Retry shortly.",
                    status_code=503,
                ) from exc

        if response is None:
            raise GooglePlacesProviderError(
                "Google Places request failed due to an upstream SSL/network error. Retry shortly.",
                status_code=503,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            logger.warning("Google Places returned an invalid JSON response during %s.", operation)
            raise GooglePlacesProviderError(
                "Google Places returned an invalid upstream response. Retry shortly.",
                status_code=502,
            ) from exc

        return payload if isinstance(payload, dict) else {}
