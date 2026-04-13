from __future__ import annotations

from app.enums import DraftStatus, LeadSourceType, LeadStatus, TemplateKey
from app.models.lead import Lead
from app.services.normalization import normalize_business_name
from app.services.outreach import OutreachService


def test_outreach_templates_and_draft_generation(db_session) -> None:
    lead = Lead(
        business_name="Auto Center Vale",
        normalized_business_name=normalize_business_name("Auto Center Vale") or "auto center vale",
        category="auto center",
        city="Sao Jose dos Campos",
        neighborhood="Centro",
        lead_source_type=LeadSourceType.GOOGLE_PLACES,
        status=LeadStatus.NEW,
        material_profile={
            "batteries": {"relevant": True, "confidence": 0.8, "matched_keywords": ["bateria"]},
        },
    )
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    service = OutreachService(db_session)
    templates = service.list_templates()
    assert len(templates) >= 4

    preview = service.preview_draft(lead.id, TemplateKey.COLD_EMAIL)
    assert preview.subject is not None
    assert "Auto Center Vale" in preview.subject
    assert "baterias" in preview.body

    draft = service.generate_draft(lead.id, TemplateKey.COLD_EMAIL, actor="test")
    drafts = service.list_drafts_for_lead(lead.id)

    assert draft.status == DraftStatus.PENDING_REVIEW
    assert len(drafts) == 1
    assert drafts[0].body == draft.body
