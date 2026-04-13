from __future__ import annotations

from app.enums import ImportBatchStatus, ImportBatchType, LeadSourceType, LeadStatus
from app.models.import_batch import ImportBatch
from app.models.lead import Lead
from app.models.raw_discovery_record import RawDiscoveryRecord
from app.services.normalization import normalize_business_name
from app.services.scoring import ScoringService


def test_scoring_service_persists_score_breakdown(db_session) -> None:
    lead = Lead(
        business_name="Centro Automotivo Forte",
        normalized_business_name=normalize_business_name("Centro Automotivo Forte") or "centro automotivo forte",
        category="oficina mecanica",
        city="Campinas",
        state="SP",
        website="https://forte.com.br",
        domain="forte.com.br",
        email="contato@forte.com.br",
        phone="+5511999999999",
        whatsapp="+5511999999999",
        lead_source_type=LeadSourceType.GOOGLE_PLACES,
        status=LeadStatus.NEW,
        material_profile={
            "batteries": {"relevant": True, "confidence": 0.9, "matched_keywords": ["bateria"]},
            "electronics": {"relevant": True, "confidence": 0.8, "matched_keywords": ["eletronica"]},
        },
    )
    db_session.add(lead)
    db_session.flush()

    batch = ImportBatch(batch_type=ImportBatchType.DISCOVERY, status=ImportBatchStatus.COMPLETED, source_provider="google_places")
    db_session.add(batch)
    db_session.flush()
    db_session.add(
        RawDiscoveryRecord(
            import_batch_id=batch.id,
            lead_id=lead.id,
            provider="google_places",
            provider_record_id="abc123",
            payload_json={},
        )
    )
    db_session.commit()
    db_session.refresh(lead)

    service = ScoringService(db_session)
    result = service.score_lead(lead.id)
    db_session.commit()

    refreshed = db_session.get(Lead, lead.id)
    assert result.lead_score >= 70
    assert refreshed is not None
    assert refreshed.lead_score == result.lead_score
    assert "material_relevance" in refreshed.score_breakdown
