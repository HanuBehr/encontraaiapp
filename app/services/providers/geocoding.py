from __future__ import annotations

from dataclasses import dataclass

import requests

from app.config import Settings


@dataclass(slots=True)
class GeocodedLocation:
    label: str
    latitude: float
    longitude: float


class GoogleGeocodingClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def resolve(self, query: str) -> GeocodedLocation:
        if not self.settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is required for location resolution.")

        response = requests.get(
            self.settings.google_geocode_base_url,
            params={
                "address": query,
                "key": self.settings.google_api_key,
                "language": "pt-BR",
                "region": "br",
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results", [])
        if not results:
            raise ValueError(f"No geocoding results found for '{query}'.")

        result = results[0]
        location = result["geometry"]["location"]
        return GeocodedLocation(
            label=result.get("formatted_address", query),
            latitude=float(location["lat"]),
            longitude=float(location["lng"]),
        )
