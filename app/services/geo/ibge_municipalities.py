from __future__ import annotations

import re

from app.services.normalization import normalize_brazilian_state, normalize_text


_CITY_STATE_SPLIT_RE = re.compile(r"\s*,\s*")

_KNOWN_MUNICIPALITY_CODES: dict[tuple[str, str], str] = {
    ("curitiba", "PR"): "4106902",
    ("sao paulo", "SP"): "3550308",
    ("santana de parnaiba", "SP"): "3547304",
    ("campinas", "SP"): "3509502",
    ("belo horizonte", "MG"): "3106200",
    ("rio de janeiro", "RJ"): "3304557",
    ("ribeirao preto", "SP"): "3543402",
    ("sao bernardo do campo", "SP"): "3548708",
    ("santo andre", "SP"): "3547809",
    ("guarulhos", "SP"): "3518800",
    ("osasco", "SP"): "3534401",
    ("barueri", "SP"): "3505708",
    ("embu das artes", "SP"): "3515004",
}


def lookup_ibge_municipality_code(city: str | None, state: str | None = None) -> str | None:
    normalized_city, normalized_state = normalize_city_state_for_ibge(city, state)
    if normalized_city is None or normalized_state is None:
        return None
    return _KNOWN_MUNICIPALITY_CODES.get((normalized_city, normalized_state))


def normalize_city_state_for_ibge(
    city: str | None,
    state: str | None = None,
) -> tuple[str | None, str | None]:
    raw_city = city.strip() if isinstance(city, str) else None
    raw_state = state.strip() if isinstance(state, str) else None

    if raw_city and "," in raw_city:
        city_parts = _CITY_STATE_SPLIT_RE.split(raw_city, maxsplit=1)
        if len(city_parts) == 2:
            raw_city = city_parts[0]
            raw_state = raw_state or city_parts[1]

    normalized_city = normalize_text(raw_city)
    normalized_state = normalize_brazilian_state(raw_state) or None
    return normalized_city, normalized_state
