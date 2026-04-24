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
_ADDRESS_LABEL_PREFIX_RE = re.compile(r"^(?:(?:endereco|endere\u00e7o|logradouro)\s*[:\-]\s*)+", re.IGNORECASE)
_ADDRESS_TRAILING_GARBAGE_RE = re.compile(
    r"(?:,\s*|\s+-\s*)(?:\d{5}-?\d{3}|\+?\d[\d().\s-]{7,})\s*$",
    re.IGNORECASE,
)
_ADDRESS_NUMERIC_PREFIX_GARBAGE_RE = re.compile(
    r"^(?:\d{2,6}\s*)+(?=(?:r\.?|rua|av\.?|avenida|al\.?|alameda|trav\.?|travessa|rod\.?|rodovia|estr\.?|estrada|pc\.?|praca|pra\u00e7a)\b)",
    re.IGNORECASE,
)
_ADDRESS_COMPLEX_COMPONENT_RE = re.compile(
    r"(?:,\s*|\s+-\s*|\s+)(?:quadra|lote|bloco|apartamento|apto|fundos|andar)\b.*$",
    re.IGNORECASE,
)
_STREET_NUMBER_RE = re.compile(r"^\d{1,6}(?:[A-Za-z]{1,2}|(?:[-/][A-Za-z0-9]{1,4}))?$")

WHATSAPP_HOST_KEYWORDS = ("wa.me", "whatsapp.com", "wa.link")
INSTAGRAM_HOST_KEYWORDS = ("instagram.com", "instagr.am")
POSTAL_CODE_RE = re.compile(r"\b\d{5}-?\d{3}\b")
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
BRAZILIAN_STATE_UFS = {
    "acre": "AC",
    "alagoas": "AL",
    "amapa": "AP",
    "amazonas": "AM",
    "bahia": "BA",
    "ceara": "CE",
    "distrito federal": "DF",
    "espirito santo": "ES",
    "goias": "GO",
    "maranhao": "MA",
    "mato grosso": "MT",
    "mato grosso do sul": "MS",
    "minas gerais": "MG",
    "para": "PA",
    "paraiba": "PB",
    "parana": "PR",
    "pernambuco": "PE",
    "piaui": "PI",
    "rio de janeiro": "RJ",
    "rio grande do norte": "RN",
    "rio grande do sul": "RS",
    "rondonia": "RO",
    "roraima": "RR",
    "santa catarina": "SC",
    "sao paulo": "SP",
    "sergipe": "SE",
    "tocantins": "TO",
}
BRAZILIAN_UFS = set(BRAZILIAN_STATE_UFS.values())
NON_BUSINESS_WEBSITE_SUFFIXES = (
    "google.com",
    "google.com.br",
    "g.page",
    "goo.gl",
    "instagram.com",
    "instagr.am",
    "facebook.com",
    "fb.com",
    "m.facebook.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "youtu.be",
    "tiktok.com",
    "wa.me",
    "whatsapp.com",
    "wa.link",
)
CLIENT_FACING_EMAIL_BLOCKLIST = {
    "meu@email.com.br",
    "email@email.com",
    "email@email.com.br",
    "test@test.com",
    "teste@teste.com",
    "example@example.com",
    "exemplo@exemplo.com",
    "exemplo@exemplo.com.br",
}
CLIENT_FACING_EMAIL_BLOCKED_DOMAINS = {
    "example.com",
    "example.com.br",
    "email.com",
    "email.com.br",
    "teste.com",
    "test.com",
    "exemplo.com",
    "exemplo.com.br",
    "invalid",
    "localhost",
}
AMBIGUOUS_STREET_COMPONENT_MARKERS = (
    "quadra",
    "lote",
    "bloco",
    "apartamento",
    "apto",
    "fundos",
    "andar",
)


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


def normalize_brazilian_state(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    upper = text.upper()
    if upper in BRAZILIAN_UFS:
        return upper
    normalized = normalize_text(text)
    if not normalized:
        return text or None
    return BRAZILIAN_STATE_UFS.get(normalized, text)


def format_street_address(street: str | None, number: str | None = None) -> str | None:
    street_name = _clean_address_text(street)
    street_number = _clean_address_text(number)
    if not street_name:
        return None
    if street_number:
        return f"{street_name}, {street_number}"
    return street_name


def split_street_and_number(
    address: str | None,
    *,
    neighborhood: str | None = None,
    city: str | None = None,
    state: str | None = None,
    postal_code: str | None = None,
) -> tuple[str | None, str | None]:
    cleaned = _clean_address_text(address)
    if not cleaned:
        return None, None
    cleaned = _ADDRESS_LABEL_PREFIX_RE.sub("", cleaned)

    cleaned = re.sub(r"(?:,\s*)?(?:brasil|brazil)\s*$", "", cleaned, flags=re.IGNORECASE).strip(" ,-")
    if postal_code:
        cleaned = re.sub(
            rf"(?:,\s*|\s+-\s*)?{re.escape(postal_code.strip())}\s*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip(" ,-")
    cleaned = POSTAL_CODE_RE.sub("", cleaned).strip(" ,-")

    state_values = [value for value in unique_preserve_order([state, normalize_brazilian_state(state)]) if value]
    city_value = _clean_address_text(city)
    if city_value:
        for state_value in state_values:
            cleaned = re.sub(
                rf"(?:,\s*|\s+-\s*){re.escape(city_value)}\s*(?:-\s*|,\s*){re.escape(state_value)}\s*$",
                "",
                cleaned,
                flags=re.IGNORECASE,
            ).strip(" ,-")
        cleaned = re.sub(
            rf"(?:,\s*|\s+-\s*){re.escape(city_value)}\s*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip(" ,-")
    for state_value in state_values:
        cleaned = re.sub(
            rf"(?:,\s*|\s+-\s*){re.escape(state_value)}\s*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip(" ,-")
    neighborhood_value = _clean_address_text(neighborhood)
    if neighborhood_value:
        cleaned = re.sub(
            rf"(?:,\s*|\s+-\s*){re.escape(neighborhood_value)}\s*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip(" ,-")

    if not cleaned:
        return None, None

    sn_match = re.match(r"^(?P<street>.+?)(?:,\s*|\s+-\s*)(?:s\/n|sn)\s*$", cleaned, flags=re.IGNORECASE)
    if sn_match:
        return _cleanup_street_candidate(sn_match.group("street")), None

    street_candidate = cleaned
    street_number: str | None = None
    number_match = re.match(r"^(?P<street>.+?)(?:,\s*|\s+-\s*)(?P<number>[^,]+?)\s*$", cleaned, flags=re.IGNORECASE)
    if number_match:
        candidate_street = _cleanup_street_candidate(number_match.group("street"))
        candidate_number = _clean_address_text(number_match.group("number"))
        if _looks_like_street_number(candidate_number, street_candidate=candidate_street):
            street_candidate = candidate_street or cleaned
            street_number = candidate_number
        else:
            street_candidate = cleaned

    return _cleanup_street_candidate(street_candidate), street_number


def is_probable_business_website(url: str | None) -> bool:
    domain = normalize_domain(url)
    return bool(domain and not is_non_business_website_domain(domain))


def is_non_business_website_domain(domain: str | None) -> bool:
    host = (domain or "").strip().lower()
    if not host:
        return True
    return any(host == suffix or host.endswith(f".{suffix}") for suffix in NON_BUSINESS_WEBSITE_SUFFIXES)


def is_probable_client_facing_email(value: str | None) -> bool:
    email = clean_email(value)
    if not email or not _EMAIL_RE.fullmatch(email):
        return False
    if email in CLIENT_FACING_EMAIL_BLOCKLIST:
        return False
    local_part, domain = email.rsplit("@", 1)
    domain = domain.lower().strip()
    if domain in CLIENT_FACING_EMAIL_BLOCKED_DOMAINS or domain.endswith(".example.com"):
        return False
    if domain.endswith("wixpress.com"):
        return False
    if "sentry" in local_part or "sentry" in domain:
        return False
    return True


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


def _clean_address_text(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip(" ,;-")
    return cleaned or None


def _cleanup_street_candidate(value: str | None) -> str | None:
    cleaned = _clean_address_text(value)
    if not cleaned:
        return None
    cleaned = _ADDRESS_LABEL_PREFIX_RE.sub("", cleaned)
    cleaned = _ADDRESS_NUMERIC_PREFIX_GARBAGE_RE.sub("", cleaned).strip(" ,-")
    cleaned = _ADDRESS_COMPLEX_COMPONENT_RE.sub("", cleaned).strip(" ,-")
    while True:
        next_value = _ADDRESS_TRAILING_GARBAGE_RE.sub("", cleaned).strip(" ,-")
        if next_value == cleaned:
            break
        cleaned = next_value
    return _clean_address_text(cleaned)


def _looks_like_street_number(value: str | None, *, street_candidate: str | None = None) -> bool:
    candidate = _clean_address_text(value)
    if not candidate:
        return False
    normalized_candidate = candidate.lower()
    if normalized_candidate in {"sn", "s/n"} or " " in candidate:
        return False
    if POSTAL_CODE_RE.fullmatch(candidate):
        return False
    digits = re.sub(r"\D", "", candidate)
    if not digits or len(digits) > 6:
        return False
    if not _STREET_NUMBER_RE.fullmatch(candidate):
        return False
    normalized_street = normalize_text(street_candidate) or ""
    if any(marker in normalized_street for marker in AMBIGUOUS_STREET_COMPONENT_MARKERS):
        return False
    return True
