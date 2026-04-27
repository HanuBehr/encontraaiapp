from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.enums import LeadSourceType, LeadStatus
from app.models.lead import Lead
from app.services.normalization import normalize_business_name
from app.services.scoring import ScoringService


def _lead(
    business_name: str,
    *,
    category: str,
    city: str = "Campinas",
    state: str = "SP",
) -> Lead:
    return Lead(
        business_name=business_name,
        normalized_business_name=normalize_business_name(business_name) or business_name.lower(),
        category=category,
        city=city,
        state=state,
        address="Rua Central, 100",
        website="https://empresa.example.com.br",
        domain="empresa.example.com.br",
        email="contato@empresa.example.com.br",
        phone="+5511999999999",
        whatsapp="+5511999999999",
        google_maps_url="https://maps.google.com/?q=empresa",
        google_place_id=f"place-{normalize_business_name(business_name)}",
        lead_source_type=LeadSourceType.GOOGLE_PLACES,
        status=LeadStatus.NEW,
    )


def test_scoring_service_is_niche_agnostic_for_core_business_types(db_session) -> None:
    leads = [
        _lead("Clinica Sorriso", category="dentista"),
        _lead("Restaurante Sabor da Casa", category="restaurante"),
        _lead("Clinica Vida", category="clinica medica"),
        _lead("Oficina Motor Sul", category="oficina mecanica"),
        _lead("Loja Bela Casa", category="loja de moveis"),
    ]
    db_session.add_all(leads)
    db_session.commit()

    service = ScoringService(db_session)
    scores = [service.score_lead(lead.id) for lead in leads]
    db_session.commit()

    lead_scores = {result.lead_score for result in scores}
    assert len(lead_scores) == 1
    assert next(iter(lead_scores)) > 70
    for result in scores:
        assert "material_relevance" not in result.breakdown
        assert "category_relevance" not in result.breakdown
        assert result.breakdown["has_phone"]["points"] > 0
        assert result.breakdown["has_website"]["points"] > 0
        assert result.breakdown["has_email"]["points"] > 0
        assert result.breakdown["has_whatsapp"]["points"] > 0
        assert result.breakdown["has_map_listing"]["points"] > 0


def test_scoring_service_prioritizes_generic_completeness_signals(db_session) -> None:
    sparse = Lead(
        business_name="Consultorio Inicial",
        normalized_business_name=normalize_business_name("Consultorio Inicial") or "consultorio inicial",
        category="dentista",
        city="Campinas",
        state="SP",
        lead_source_type=LeadSourceType.GOOGLE_PLACES,
        status=LeadStatus.NEW,
    )
    rich = _lead("Moveis Premium", category="loja de moveis")
    rich.last_enriched_at = datetime.now(timezone.utc) - timedelta(days=7)
    rich.rating = 4.8
    rich.review_count = 128
    db_session.add_all([sparse, rich])
    db_session.commit()

    service = ScoringService(db_session)
    sparse_result = service.score_lead(sparse.id)
    rich_result = service.score_lead_instance(rich)
    db_session.commit()

    assert rich_result.lead_score > sparse_result.lead_score
    assert sparse_result.breakdown["has_email"]["points"] == 0
    assert sparse_result.breakdown["has_address"]["points"] == 0
    assert rich_result.breakdown["reputation_signals"]["points"] == 4
    assert rich_result.breakdown["freshness"]["points"] > 0
    assert rich_result.breakdown["core_field_completeness"]["points"] > sparse_result.breakdown["core_field_completeness"]["points"]
