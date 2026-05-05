from __future__ import annotations

from app.enums import CompanySizeFit, LeadSourceType, LeadStatus, TradeType
from app.models.lead import Lead
from app.services.normalization import normalize_business_name


def _seed_lead(
    db_session,
    *,
    business_name: str,
    city: str,
    email: str | None = None,
    whatsapp: str | None = None,
    cnpj: str | None = None,
    legal_name: str | None = None,
    cnpj_match_status: str = "unknown",
    cnpj_match_confidence: float | None = None,
    cnpj_source_provider: str | None = None,
    cnpj_metadata_json: dict | None = None,
    status: LeadStatus = LeadStatus.NEW,
    do_not_contact: bool = False,
    company_size_fit: CompanySizeFit = CompanySizeFit.UNKNOWN,
    trade_type: TradeType = TradeType.UNKNOWN,
    is_blocked: bool = False,
    blocked_reason: str | None = None,
) -> Lead:
    lead = Lead(
        business_name=business_name,
        normalized_business_name=normalize_business_name(business_name) or business_name.lower(),
        category="oficina mecânica",
        city=city,
        state="SP",
        lead_source_type=LeadSourceType.GOOGLE_PLACES,
        email=email,
        whatsapp=whatsapp,
        cnpj=cnpj,
        legal_name=legal_name,
        cnpj_match_status=cnpj_match_status,
        cnpj_match_confidence=cnpj_match_confidence,
        cnpj_source_provider=cnpj_source_provider,
        cnpj_metadata_json=cnpj_metadata_json or {},
        status=status,
        do_not_contact=do_not_contact,
        company_size_fit=company_size_fit.value,
        trade_type=trade_type.value,
        is_blocked=is_blocked,
        blocked_reason=blocked_reason,
    )
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)
    return lead


def test_list_leads_with_filters(client, db_session) -> None:
    _seed_lead(db_session, business_name="Oficina A", city="Sao Paulo", email="a@example.com")
    _seed_lead(
        db_session,
        business_name="Oficina B",
        city="Campinas",
        whatsapp="+5511999999999",
        do_not_contact=True,
    )

    response = client.get("/leads", params={"city": "Sao Paulo", "has_email": True})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["business_name"] == "Oficina A"


def test_list_leads_with_quality_filters(client, db_session) -> None:
    _seed_lead(
        db_session,
        business_name="Casa de Tintas A",
        city="Campinas",
        company_size_fit=CompanySizeFit.IDEAL_SME,
        trade_type=TradeType.VAREJO,
    )
    _seed_lead(
        db_session,
        business_name="Distribuidora B",
        city="Campinas",
        company_size_fit=CompanySizeFit.POSSIBLE_SME,
        trade_type=TradeType.DISTRIBUIDORA,
    )

    response = client.get(
        "/leads",
        params={
            "company_size_fit": "ideal_sme",
            "trade_type": "varejo",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["business_name"] == "Casa de Tintas A"
    assert payload["items"][0]["company_size_fit"] == "ideal_sme"
    assert payload["items"][0]["trade_type"] == "varejo"


def test_list_leads_blocked_filter_and_metadata(client, db_session) -> None:
    _seed_lead(db_session, business_name="Loja Permitida", city="Campinas")
    _seed_lead(
        db_session,
        business_name="Rede Bloqueada",
        city="Campinas",
        is_blocked=True,
        blocked_reason="Known large chain",
    )

    default_response = client.get("/leads")
    include_response = client.get("/leads", params={"blocked": "include"})
    only_response = client.get("/leads", params={"blocked": "only"})

    assert default_response.status_code == 200
    assert default_response.json()["total"] == 1
    assert default_response.json()["items"][0]["business_name"] == "Loja Permitida"
    assert include_response.status_code == 200
    assert include_response.json()["total"] == 2
    blocked_item = next(item for item in include_response.json()["items"] if item["business_name"] == "Rede Bloqueada")
    assert blocked_item["is_blocked"] is True
    assert blocked_item["blocked_reason"] == "Known large chain"
    assert only_response.status_code == 200
    assert only_response.json()["total"] == 1
    assert only_response.json()["items"][0]["business_name"] == "Rede Bloqueada"


def test_get_and_update_lead(client, db_session) -> None:
    lead = _seed_lead(
        db_session,
        business_name="Auto Eletrica Z",
        city="Santos",
        cnpj="37335118000180",
        legal_name="Auto Eletrica Z LTDA",
    )

    detail_response = client.get(f"/leads/{lead.id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["business_name"] == "Auto Eletrica Z"
    assert detail_response.json()["cnpj"] == "37335118000180"
    assert detail_response.json()["legal_name"] == "Auto Eletrica Z LTDA"
    assert detail_response.json()["cnpj_match_status"] == "unknown"

    update_response = client.patch(
        f"/leads/{lead.id}",
        json={
            "status": "reviewed",
            "notes": "Contato inicial revisado.",
            "tags": ["baterias", "prioridade_alta"],
            "do_not_contact": True,
        },
    )

    assert update_response.status_code == 200
    payload = update_response.json()
    assert payload["status"] == "do_not_contact"
    assert payload["do_not_contact"] is True
    assert "prioridade_alta" in payload["tags"]
    actions = [item["action"] for item in payload["activity_logs"]]
    assert "status_changed" in actions
    assert "note_added" in actions
    assert "lead_updated" in actions


def test_approve_cnpj_candidate_endpoint_confirms_reviewable_candidate(client, db_session) -> None:
    lead = _seed_lead(
        db_session,
        business_name="Wawa Moveis",
        city="Guarulhos",
        cnpj_match_status="needs_review",
        cnpj_match_confidence=1.0,
        cnpj_source_provider="cnpja_commercial",
        cnpj_metadata_json={
            "reason_code": "company_search_needs_review",
            "candidate_summary": {
                "cnpj": "17247065000139",
                "legal_name": "Wawa Moveis Ltda",
                "trade_name": "Wawa Moveis",
                "city": "Guarulhos",
                "state": "SP",
                "provider": "cnpja_commercial",
                "match_confidence": 1.0,
                "blocked_from_autofill_reason": "ambiguous_top_candidates",
            },
        },
    )

    response = client.post(f"/leads/{lead.id}/approve-cnpj-candidate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["cnpj"] == "17247065000139"
    assert payload["legal_name"] == "Wawa Moveis Ltda"
    assert payload["cnpj_match_status"] == "matched"
    assert payload["cnpj_match_confidence"] == 1.0
    assert payload["cnpj_metadata_json"]["approved_manually"] is True
    assert payload["cnpj_metadata_json"]["previous_status"] == "needs_review"


def test_approve_cnpj_candidate_endpoint_rejects_missing_candidate(client, db_session) -> None:
    lead = _seed_lead(
        db_session,
        business_name="Lead Revisao",
        city="Sao Paulo",
        cnpj_match_status="needs_review",
        cnpj_match_confidence=0.78,
        cnpj_metadata_json={
            "reason_code": "company_search_needs_review",
            "candidate_summary": {
                "cnpj": "***",
                "legal_name": "Lead Revisao Ltda",
                "provider": "cnpja_commercial",
                "match_confidence": 0.78,
                "blocked_from_autofill_reason": "provider_preview_masked",
            },
        },
    )

    response = client.post(f"/leads/{lead.id}/approve-cnpj-candidate")

    assert response.status_code == 400
    assert response.json()["detail"] == "Nenhum CNPJ revisável disponível para este lead."
