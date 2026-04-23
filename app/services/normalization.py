from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from html import unescape
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import phonenumbers


_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.IGNORECASE)
_SPACED_EMAIL_RE = re.compile(
    r"(?P<local>[A-Z0-9._%+\-]{2,})\s*@\s*(?P<domain>[A-Z0-9\-]+(?:\s*\.\s*[A-Z0-9\-]+)+)",
    re.IGNORECASE,
)
_EMAIL_AT_TOKEN = r"(?:@|\[\s*at\s*\]|\(\s*at\s*\)|\[\s*arroba\s*\]|\(\s*arroba\s*\)|\s+at\s+|\s+arroba\s+)"
_EMAIL_DOT_TOKEN = r"(?:\.|\[\s*dot\s*\]|\(\s*dot\s*\)|\[\s*ponto\s*\]|\(\s*ponto\s*\)|\s+dot\s+|\s+ponto\s+)"
_EMAIL_OBFUSCATED_RE = re.compile(
    rf"\b(?P<local>[A-Z0-9._%+\-]{{2,}})"
    rf"\s*{_EMAIL_AT_TOKEN}\s*"
    rf"(?P<domain>[A-Z0-9\-]+(?:\s*{_EMAIL_DOT_TOKEN}\s*[A-Z0-9\-]+)*)"
    rf"\s*{_EMAIL_DOT_TOKEN}\s*"
    rf"(?P<tld>[A-Z]{{2,}}(?:\s*{_EMAIL_DOT_TOKEN}\s*[A-Z]{{2,}})?)\b",
    re.IGNORECASE,
)
_EMAIL_DOT_TOKEN_RE = re.compile(_EMAIL_DOT_TOKEN, re.IGNORECASE)
_PHONE_RE = re.compile(
    r"(?:(?:\+?55)\s*)?(?:\(?\d{2}\)?\s*)?(?:9?\d{4})[\s\-]?\d{4}",
    re.IGNORECASE,
)

WHATSAPP_HOST_KEYWORDS = ("wa.me", "whatsapp.com", "wa.link")
INSTAGRAM_HOST_KEYWORDS = ("instagram.com", "instagr.am")
CONTACT_URL_HINTS = ("contato", "contact", "fale", "atendimento", "suporte")
ENRICHMENT_PAGE_HINTS = CONTACT_URL_HINTS + (
    "sobre",
    "about",
    "empresa",
    "institucional",
    "quem somos",
    "nossa historia",
)
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
    try:
        if base_url:
            candidate = urljoin(base_url, candidate)
        parsed = urlparse(candidate if "://" in candidate else f"https://{candidate}")
    except ValueError:
        return None
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
    decoded = unquote(unescape(value))
    return decoded.strip().strip("<>()[]{}\"'.,;:").lower() or None


def unique_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def extract_emails(text: str) -> list[str]:
    decoded_text = unquote(unescape(text or ""))
    return unique_preserve_order(
        email
        for email in (clean_email(match.group(0)) for match in _EMAIL_RE.finditer(decoded_text))
        if email
    )


def extract_spaced_emails(text: str) -> list[str]:
    decoded_text = unquote(unescape(text or ""))
    candidates: list[str] = []
    for match in _SPACED_EMAIL_RE.finditer(decoded_text):
        email = clean_email(f"{match.group('local')}@{match.group('domain')}")
        if email and _EMAIL_RE.fullmatch(email.replace(" ", "")):
            normalized_email = clean_email(email.replace(" ", ""))
            if normalized_email:
                candidates.append(normalized_email)
    return unique_preserve_order(candidates)


def _normalize_obfuscated_email_part(value: str) -> str:
    dotted = _EMAIL_DOT_TOKEN_RE.sub(".", value)
    return re.sub(r"\s+", "", dotted).strip(".").lower()


def extract_obfuscated_emails(text: str) -> list[str]:
    decoded_text = unquote(unescape(text or ""))
    candidates: list[str] = []
    for match in _EMAIL_OBFUSCATED_RE.finditer(decoded_text):
        local = (match.group("local") or "").strip().lower()
        domain = _normalize_obfuscated_email_part(match.group("domain") or "")
        tld = _normalize_obfuscated_email_part(match.group("tld") or "")
        email = clean_email(f"{local}@{domain}.{tld}")
        if email and _EMAIL_RE.fullmatch(email):
            candidates.append(email)
    return unique_preserve_order(candidates)


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


def _matches_page_hints(
    url: str | None,
    *,
    label: str | None = None,
    hints: Iterable[str],
) -> bool:
    candidates: list[str] = []
    canonical = canonicalize_url(url)
    if canonical:
        normalized_url = normalize_text(canonical)
        if normalized_url:
            candidates.append(normalized_url)
    normalized_label = normalize_text(label)
    if normalized_label:
        candidates.append(normalized_label)
    return any(hint in candidate for candidate in candidates for hint in hints)


def is_contact_like_url(url: str | None, *, label: str | None = None) -> bool:
    return _matches_page_hints(url, label=label, hints=CONTACT_URL_HINTS)


def is_enrichment_candidate_url(url: str | None, *, label: str | None = None) -> bool:
    return _matches_page_hints(url, label=label, hints=ENRICHMENT_PAGE_HINTS)
