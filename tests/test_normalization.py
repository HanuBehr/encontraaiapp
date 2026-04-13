from __future__ import annotations

from app.services.normalization import normalize_business_name, normalize_domain, normalize_phone_br


def test_normalize_business_name_removes_accents_and_symbols() -> None:
    assert normalize_business_name("Oficina Mecânica São José!") == "oficina mecanica sao jose"


def test_normalize_domain_strips_scheme_and_www() -> None:
    assert normalize_domain("https://www.exemplo.com.br/contato") == "exemplo.com.br"


def test_normalize_phone_br_returns_e164() -> None:
    assert normalize_phone_br("(11) 98765-4321") == "+5511987654321"
