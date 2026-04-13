from __future__ import annotations

from app.enums import LeadSourceType, LeadStatus
from app.models.lead import Lead
from app.services.dedupe import DedupeService
from app.services.normalization import normalize_business_name


def test_dedupe_preview_and_merge(db_session) -> None:
    lead_a = Lead(
        business_name="Oficina Silva",
        normalized_business_name=normalize_business_name("Oficina Silva") or "oficina silva",
        category="oficina mecanica",
        city="Sao Paulo",
        state="SP",
        phone="+5511999999999",
        email="contato@silva.com.br",
        lead_source_type=LeadSourceType.GOOGLE_PLACES,
        status=LeadStatus.NEW,
    )
    lead_b = Lead(
        business_name="Oficina Silva",
        normalized_business_name=normalize_business_name("Oficina Silva") or "oficina silva",
        category="auto eletrica",
        city="Sao Paulo",
        state="SP",
        phone="+5511999999999",
        whatsapp="+5511999999999",
        website="https://silva.com.br",
        domain="silva.com.br",
        lead_source_type=LeadSourceType.GOOGLE_PLACES,
        status=LeadStatus.NEW,
    )
    db_session.add_all([lead_a, lead_b])
    db_session.commit()
    db_session.refresh(lead_a)
    db_session.refresh(lead_b)

    service = DedupeService(db_session)
    preview = service.preview_duplicates()

    assert preview.total_candidates == 1
    assert "normalized_business_name" in preview.items[0].reasons
    assert "phone" in preview.items[0].reasons

    result = service.dedupe_pair(
        lead_a_id=lead_a.id,
        lead_b_id=lead_b.id,
        canonical_lead_id=lead_a.id,
        actor="test",
    )

    refreshed_canonical = db_session.get(Lead, lead_a.id)
    refreshed_duplicate = db_session.get(Lead, lead_b.id)

    assert result.canonical_lead_id == lead_a.id
    assert refreshed_canonical is not None
    assert refreshed_duplicate is not None
    assert refreshed_canonical.whatsapp == "+5511999999999"
    assert refreshed_duplicate.is_duplicate is True
    assert refreshed_duplicate.duplicate_of_lead_id == lead_a.id
