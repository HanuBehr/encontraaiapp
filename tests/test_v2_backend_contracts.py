from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

from openpyxl import load_workbook

from app.enums import ImportBatchStatus, ImportBatchType, LeadSourceType, LeadStatus
from app.models.assignment_rule import AssignmentRule
from app.models.import_batch import ImportBatch
from app.models.lead import Lead
from app.models.market_taxonomy import MarketSegment, MarketSubsegment
from app.models.organization import Organization
from app.models.raw_discovery_record import RawDiscoveryRecord
from app.models.sales_region import SalesRegion
from app.models.sales_rep import SalesRep
from app.services.normalization import normalize_business_name


def _default_org() -> Organization:
    return Organization(slug="default", name="Default Organization", display_name="Default Organization")


def _lead(
    name: str,
    *,
    organization: Organization,
    city: str = "Campinas",
    state: str = "SP",
    category: str = "loja de tintas",
    instagram: str | None = None,
    status: LeadStatus = LeadStatus.NEW,
) -> Lead:
    return Lead(
        organization=organization,
        business_name=name,
        normalized_business_name=normalize_business_name(name) or name.lower(),
        category=category,
        city=city,
        state=state,
        instagram=instagram,
        lead_source_type=LeadSourceType.GOOGLE_PLACES,
        status=status,
    )


def _workbook_names(payload: bytes) -> list[str]:
    workbook = load_workbook(BytesIO(payload))
    return [
        row[0].value
        for row in workbook["Empresas"].iter_rows(min_row=2, max_col=1)
        if row[0].value
    ]


def test_list_leads_supports_state_instagram_and_sort(client, db_session) -> None:
    organization = _default_org()
    beta = _lead(
        "Beta Tintas",
        organization=organization,
        state="SP",
        instagram="https://instagram.com/beta",
    )
    alpha = _lead(
        "Alpha Tintas",
        organization=organization,
        state="SP",
        instagram="https://instagram.com/alpha",
    )
    rio = _lead(
        "Rio Tintas",
        organization=organization,
        city="Rio de Janeiro",
        state="RJ",
        instagram="https://instagram.com/rio",
    )
    db_session.add_all([organization, beta, alpha, rio])
    db_session.commit()

    response = client.get(
        "/leads",
        params={
            "state": "SP",
            "has_instagram": True,
            "sort_by": "business_name",
            "sort_dir": "asc",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert [item["business_name"] for item in payload["items"]] == ["Alpha Tintas", "Beta Tintas"]
    assert [item["instagram"] for item in payload["items"]] == [
        "https://instagram.com/alpha",
        "https://instagram.com/beta",
    ]


def test_lead_options_return_v2_filter_data(client, db_session) -> None:
    organization = _default_org()
    sales_rep = SalesRep(organization=organization, name="Ana Comercial", email="ana@example.com")
    region = SalesRegion(
        organization=organization,
        name="Campinas",
        region_type="mesoregion",
        state="SP",
        code="sp-campinas",
    )
    segment = MarketSegment(organization=organization, key="varejo", name="Varejo", sort_order=1)
    subsegment = MarketSubsegment(
        organization=organization,
        segment=segment,
        key="loja_de_tintas",
        name="Loja de Tintas",
        sort_order=1,
    )
    lead = _lead("Casa Campinas", organization=organization, status=LeadStatus.REVIEWED)
    db_session.add_all([organization, sales_rep, region, segment, subsegment, lead])
    db_session.commit()

    response = client.get("/leads/options")

    assert response.status_code == 200
    payload = response.json()
    assert "Campinas" in payload["cities"]
    assert "SP" in payload["states"]
    assert "reviewed" in payload["statuses"]
    assert "ideal_sme" in payload["target_fit_values"]
    assert "varejo" in payload["trade_type_values"]
    assert payload["assigned_reps"] == [{"id": sales_rep.id, "name": "Ana Comercial"}]
    assert payload["sales_regions"][0]["code"] == "sp-campinas"
    assert payload["market_segments"] == [{"id": segment.id, "name": "Varejo", "key": "varejo"}]
    assert payload["market_subsegments"] == [
        {
            "id": subsegment.id,
            "name": "Loja de Tintas",
            "key": "loja_de_tintas",
            "market_segment_id": segment.id,
        }
    ]


def test_latest_import_batch_endpoint_and_scope_resolver(client, db_session) -> None:
    organization = _default_org()
    old_lead = _lead("Old Import Lead", organization=organization)
    new_lead = _lead("New Import Lead", organization=organization)
    old_batch = ImportBatch(
        batch_type=ImportBatchType.DISCOVERY,
        status=ImportBatchStatus.COMPLETED,
        source_provider="google_places",
        source_query="old",
        record_count=1,
        completed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    new_batch = ImportBatch(
        batch_type=ImportBatchType.DISCOVERY,
        status=ImportBatchStatus.COMPLETED,
        source_provider="google_places",
        source_query="new",
        record_count=1,
        completed_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    db_session.add_all([organization, old_lead, new_lead, old_batch, new_batch])
    db_session.flush()
    db_session.add_all(
        [
            RawDiscoveryRecord(
                import_batch_id=old_batch.id,
                lead_id=old_lead.id,
                provider="google_places",
                payload_json={},
            ),
            RawDiscoveryRecord(
                import_batch_id=new_batch.id,
                lead_id=new_lead.id,
                provider="google_places",
                payload_json={},
            ),
        ]
    )
    db_session.commit()

    latest_response = client.get("/leads/import-batches/latest")
    scope_response = client.post("/leads/resolve-scope", json={"latest_import_batch": True})

    assert latest_response.status_code == 200
    assert latest_response.json()["id"] == new_batch.id
    assert latest_response.json()["lead_ids"] == [new_lead.id]
    assert scope_response.status_code == 200
    assert scope_response.json()["scope_type"] == "latest_import_batch"
    assert scope_response.json()["lead_ids"] == [new_lead.id]
    assert scope_response.json()["import_batch"]["id"] == new_batch.id


def test_batch_assign_wraps_existing_assignment_service(client, db_session) -> None:
    organization = _default_org()
    sales_rep = SalesRep(organization=organization, name="Ana Comercial")
    region = SalesRegion(
        organization=organization,
        name="Campinas",
        region_type="mesoregion",
        state="SP",
        cities_json=["Campinas"],
    )
    segment = MarketSegment(organization=organization, key="varejo", name="Varejo")
    subsegment = MarketSubsegment(
        organization=organization,
        segment=segment,
        key="loja_de_tintas",
        name="Loja de Tintas",
        keywords_json=["tintas"],
    )
    rule = AssignmentRule(
        organization=organization,
        name="Campinas Tintas",
        sales_region=region,
        market_segment=segment,
        market_subsegment=subsegment,
        sales_rep=sales_rep,
    )
    lead = _lead("Casa das Tintas", organization=organization, city="Campinas", state="SP")
    db_session.add_all([organization, sales_rep, region, segment, subsegment, rule, lead])
    db_session.commit()

    response = client.post("/leads/batch/assign", json={"lead_ids": [lead.id]})

    assert response.status_code == 200
    payload = response.json()
    assert payload["processed"] == 1
    assert payload["changed"] == 1
    assert payload["summary"]["scope_type"] == "lead_ids"
    assert payload["results"][0]["suggestion"]["assigned_sales_rep_id"] == sales_rep.id
    db_session.refresh(lead)
    assert lead.assigned_sales_rep_id == sales_rep.id
    assert lead.sales_region_id == region.id
    assert lead.market_subsegment_id == subsegment.id


def test_scoped_export_accepts_lead_ids_filters_and_latest_batch(client, db_session) -> None:
    organization = _default_org()
    alpha = _lead(
        "Alpha Export",
        organization=organization,
        state="SP",
        instagram="https://instagram.com/alpha",
    )
    beta = _lead("Beta Export", organization=organization, state="RJ")
    batch = ImportBatch(
        batch_type=ImportBatchType.DISCOVERY,
        status=ImportBatchStatus.COMPLETED,
        source_provider="google_places",
        source_query="export",
        record_count=1,
        completed_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
    )
    db_session.add_all([organization, alpha, beta, batch])
    db_session.flush()
    db_session.add(
        RawDiscoveryRecord(
            import_batch_id=batch.id,
            lead_id=beta.id,
            provider="google_places",
            payload_json={},
        )
    )
    db_session.commit()

    selected_response = client.post("/exports/excel", json={"lead_ids": [alpha.id]})
    filtered_response = client.post(
        "/exports/excel",
        json={
            "filters": {
                "state": "SP",
                "has_instagram": True,
                "sort_by": "business_name",
                "sort_dir": "asc",
            }
        },
    )
    latest_response = client.post("/exports/excel", json={"latest_import_batch": True})

    assert selected_response.status_code == 200
    assert filtered_response.status_code == 200
    assert latest_response.status_code == 200
    assert _workbook_names(selected_response.content) == ["Alpha Export"]
    assert _workbook_names(filtered_response.content) == ["Alpha Export"]
    assert _workbook_names(latest_response.content) == ["Beta Export"]
