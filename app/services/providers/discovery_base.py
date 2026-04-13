from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.schemas.discovery import DiscoveryLeadCandidate


@dataclass(slots=True)
class ProviderLeadResult:
    candidate: DiscoveryLeadCandidate
    raw_payload: dict[str, Any]
    provider_record_id: str | None
    source_url: str | None


class DiscoveryProvider(ABC):
    @abstractmethod
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
        raise NotImplementedError
