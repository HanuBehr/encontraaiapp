from __future__ import annotations

from typing import Any

import requests

from app.config import Settings
from app.enums import LeadSourceType
from app.schemas.discovery import DiscoveryLeadCandidate
from app.services.normalization import normalize_business_name, normalize_domain, normalize_phone_br
from app.services.providers.discovery_base import DiscoveryProvider, ProviderLeadResult


class GooglePlacesProvider(DiscoveryProvider):
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
            raise ValueError("GOOGLE_API_KEY is required for discovery.")

        response = requests.post(
            f"{self.settings.google_places_base_url}/places:searchText",
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.settings.google_api_key,
                "X-Goog-FieldMask": self.FIELD_MASK,
            },
            json={
                "textQuery": f"{search_term} em {location_label}",
                "languageCode": "pt-BR",
                "regionCode": "BR",
                "maxResultCount": max_results,
                "locationBias": {
                    "circle": {
                        "center": {"latitude": latitude, "longitude": longitude},
                        "radius": float(radius_m),
                    }
                },
            },
            timeout=30,
        )
        response.raise_for_status()

        payload = response.json()
        places = payload.get("places", [])
        return [self._to_result(place) for place in places]

    def _to_result(self, place: dict[str, Any]) -> ProviderLeadResult:
        business_name = ((place.get("displayName") or {}).get("text") or "").strip()
        address_components = place.get("addressComponents") or []
        phone = normalize_phone_br(place.get("nationalPhoneNumber"))
        website = place.get("websiteUri")
        google_maps_url = place.get("googleMapsUri")

        candidate = DiscoveryLeadCandidate(
            business_name=business_name,
            normalized_business_name=normalize_business_name(business_name) or business_name.lower(),
            category=self._extract_category(place),
            address=place.get("formattedAddress"),
            neighborhood=self._extract_component(address_components, {"sublocality", "sublocality_level_1", "neighborhood"}),
            city=self._extract_component(address_components, {"locality", "administrative_area_level_2"}),
            state=self._extract_component(address_components, {"administrative_area_level_1"}),
            postal_code=self._extract_component(address_components, {"postal_code"}),
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
