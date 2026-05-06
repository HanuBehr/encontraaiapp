from __future__ import annotations

from dataclasses import dataclass

from app.services.normalization import normalize_text


@dataclass(frozen=True, slots=True)
class CategoryCNAEHint:
    key: str
    label: str
    activity_ids: tuple[str, ...]
    keywords: tuple[str, ...]
    category_terms: tuple[str, ...]


_CATEGORY_CNAE_HINTS: tuple[CategoryCNAEHint, ...] = (
    CategoryCNAEHint(
        key="pet_shop",
        label="Pet shop",
        activity_ids=("4789004", "9609208"),
        keywords=("pet shop", "racoes", "banho e tosa", "produtos para animais"),
        category_terms=("pet shop", "petshop", "banho e tosa", "pet", "clinica veterinaria"),
    ),
    CategoryCNAEHint(
        key="furniture_retail",
        label="Loja de moveis",
        activity_ids=("4754701",),
        keywords=("moveis", "colchoes", "decoracao", "planejados"),
        category_terms=("moveis", "movel", "moveleira", "marcenaria"),
    ),
    CategoryCNAEHint(
        key="construction_materials",
        label="Material de construcao",
        activity_ids=("4744099",),
        keywords=("materiais de construcao", "cimento", "acabamentos", "hidraulica", "ferragens"),
        category_terms=("material de construcao", "materiais de construcao", "construcao", "ferragens"),
    ),
    CategoryCNAEHint(
        key="electronics_repair",
        label="Assistencia tecnica",
        activity_ids=("9512600",),
        keywords=("assistencia tecnica", "reparo", "manutencao", "celular", "eletronicos"),
        category_terms=("assistencia tecnica", "celular", "eletronica", "reparo", "conserto"),
    ),
    CategoryCNAEHint(
        key="automotive_repair",
        label="Oficina mecanica",
        activity_ids=("4520001",),
        keywords=("oficina mecanica", "manutencao automotiva", "auto center", "centro automotivo"),
        category_terms=("oficina", "mecanica", "reparo automotivo", "auto center", "centro automotivo"),
    ),
)


def find_category_cnae_hint(category: str | None) -> CategoryCNAEHint | None:
    normalized_category = normalize_text(category)
    if not normalized_category:
        return None

    for hint in _CATEGORY_CNAE_HINTS:
        if any(term in normalized_category for term in hint.category_terms):
            return hint
    return None


def category_activity_matches(
    category: str | None,
    *,
    primary_activity: str | None,
    main_activity_id: str | None = None,
    side_activity_ids: list[str] | tuple[str, ...] | None = None,
) -> bool:
    hint = find_category_cnae_hint(category)
    if hint is None:
        return False

    normalized_activity = normalize_text(primary_activity)
    if normalized_activity and any(keyword in normalized_activity for keyword in hint.keywords):
        return True

    candidate_ids = {
        normalized
        for normalized in (
            _normalize_cnae_id(main_activity_id),
            *(_normalize_cnae_id(value) for value in (side_activity_ids or [])),
        )
        if normalized
    }
    return bool(candidate_ids.intersection(hint.activity_ids))


def _normalize_cnae_id(value: str | None) -> str | None:
    if not value:
        return None
    digits = "".join(character for character in str(value) if character.isdigit())
    return digits or None
