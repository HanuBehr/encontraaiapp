from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from urllib.parse import parse_qs, urljoin, urlparse

import phonenumbers


_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.IGNORECASE)
_PHONE_RE = re.compile(
    r"(?:(?:\+?55)\s*)?(?:\(?\d{2}\)?\s*)?(?:9?\d{4})[\s\-]?\d{4}",
    re.IGNORECASE,
)

WHATSAPP_HOST_KEYWORDS = ("wa.me", "whatsapp.com", "wa.link")
INSTAGRAM_HOST_KEYWORDS = ("instagram.com", "instagr.am")
CONTACT_URL_HINTS = ("contato", "contact", "fale", "atendimento", "suporte")
MATERIAL_SIGNAL_KEYWORDS: dict[str, tuple[str, ...]] = {
    "catalytic_converters": (
        "catalisador",
        "catalisadores",
        "catalytic converter",
        "escapamento",
    ),
    "batteries": (
        "bateria",
        "baterias",
        "bateria automotiva",
        "acumulador",
    ),
    "electronics": (
        "eletronica",
        "eletronico",
        "placa mae",
        "placa-mãe",
        "cpu",
        "hd",
        "ssd",
        "notebook",
        "computador",
        "celular",
    ),
    "repair_waste": (
        "manutencao",
        "manutenção",
        "conserto",
        "assistencia tecnica",
        "assistência técnica",
        "oficina",
        "sucata",
        "residuo",
        "resíduo",
        "descarte",
        "logistica reversa",
        "logística reversa",
    ),
}


def normalize_text(value: str | None) -> str | None:
    if not value:
        return None
    normalized = unicodedata.normalize("NFKD", value)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower().strip()
    normalized = _NON_ALNUM_RE.sub(" ", normalized)
    return " ".join(normalized.split()) or None


def normalize_business_name(value: str | None) -> str | None:
    return normalize_text(value)


def canonicalize_url(url: str | None, *, base_url: str | None = None) -> str | None:
    if not url:
        return None
    candidate = url.strip()
    if not candidate:
        return None
    if base_url:
        candidate = urljoin(base_url, candidate)
    parsed = urlparse(candidate if "://" in candidate else f"https://{candidate}")
    if not parsed.netloc:
        return None
    return parsed._replace(fragment="").geturl()


def normalize_domain(url: str | None) -> str | None:
    canonical = canonicalize_url(url)
    if not canonical:
        return None
    parsed = urlparse(canonical)
    host = parsed.netloc.lower().strip()
    if host.startswith("www."):
        host = host[4:]
    return host or None


def normalize_phone_br(value: str | None) -> str | None:
    if not value:
        return None
    try:
        number = phonenumbers.parse(value, "BR")
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_possible_number(number):
        return None
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


def clean_email(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().lower() or None


def unique_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def extract_emails(text: str) -> list[str]:
    return unique_preserve_order(
        email
        for email in (clean_email(match.group(0)) for match in _EMAIL_RE.finditer(text or ""))
        if email
    )


def extract_phone_candidates(text: str) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    seen: set[str] = set()
    for match in _PHONE_RE.finditer(text or ""):
        raw_value = match.group(0).strip()
        normalized_value = normalize_phone_br(raw_value)
        if not normalized_value or normalized_value in seen:
            continue
        seen.add(normalized_value)
        results.append((raw_value, normalized_value))
    return results


def extract_whatsapp_from_url(url: str | None) -> tuple[str, str] | None:
    canonical = canonicalize_url(url)
    if not canonical:
        return None
    parsed = urlparse(canonical)
    host = parsed.netloc.lower()
    if not any(keyword in host for keyword in WHATSAPP_HOST_KEYWORDS):
        return None

    digits = ""
    if "wa.me" in host or "wa.link" in host:
        digits = re.sub(r"\D", "", parsed.path)
    else:
        query = parse_qs(parsed.query)
        digits = re.sub(r"\D", "", (query.get("phone", [""])[0]))

    if not digits:
        return None
    normalized_value = normalize_phone_br(digits)
    if not normalized_value:
        return None
    return canonical, normalized_value


def extract_instagram_links(urls: Iterable[str]) -> list[str]:
    normalized_links: list[str] = []
    for url in urls:
        canonical = canonicalize_url(url)
        if not canonical:
            continue
        host = urlparse(canonical).netloc.lower()
        if any(keyword in host for keyword in INSTAGRAM_HOST_KEYWORDS):
            normalized_links.append(canonical.rstrip("/"))
    return unique_preserve_order(normalized_links)


def infer_material_signals(text: str) -> dict[str, dict[str, object]]:
    normalized_text = normalize_text(text) or ""
    signal_payload: dict[str, dict[str, object]] = {}

    for signal_name, keywords in MATERIAL_SIGNAL_KEYWORDS.items():
        matches = [keyword for keyword in keywords if normalize_text(keyword) and normalize_text(keyword) in normalized_text]
        confidence = min(1.0, 0.35 + (0.2 * len(matches))) if matches else 0.0
        signal_payload[signal_name] = {
            "relevant": bool(matches),
            "confidence": round(confidence, 2),
            "matched_keywords": unique_preserve_order(matches),
        }

    return signal_payload


def normalize_tags(tags: Iterable[str] | None) -> list[str]:
    if tags is None:
        return []
    cleaned = [tag.strip() for tag in tags if tag and tag.strip()]
    return unique_preserve_order(cleaned)


def is_contact_like_url(url: str | None) -> bool:
    canonical = canonicalize_url(url)
    if not canonical:
        return False
    normalized = normalize_text(canonical) or ""
    return any(hint in normalized for hint in CONTACT_URL_HINTS)
