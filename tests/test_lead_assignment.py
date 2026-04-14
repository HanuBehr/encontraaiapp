from __future__ import annotations

from sqlalchemy import inspect

from app.enums import LeadSourceType, LeadStatus
from app.models.assignment_rule import AssignmentRule
from app.models.lead import Lead
from app.models.market_taxonomy import MarketSegment, MarketSubsegment
from app.models.organization import Organization
from app.models.sales_region import SalesRegion
from app.models.sales_rep import SalesRep
from app.services.lead_assignment import LeadAssignmentService
from app.services.normalization import normalize_business_name


def _organization(slug: str) -> Organization:
    return Organization(slug=slug, name=slug.title(), display_name=slug.title())


def _lead(
    business_name: str,
    *,
    organization: Organization | None,
    city: str | None = "Sao Paulo",
    state: str | None = "SP",
    category: str | None = "loja de tintas",
) -> Lead:
    return Lead(
        organization=organization,
        business_name=business_name,
        normalized_business_name=normalize_business_name(business_name) or business_name.lower(),
        category=category,
        city=city,
        state=state,
        domain="casa-alpha.example",
        lead_source_type=LeadSourceType.GOOGLE_PLACES,
        status=LeadStatus.NEW,
    )


def _assignment_fixture(db_session):
    organization = _organization("garin")
    other_organization = _organization("other-client")
    sales_rep = SalesRep(organization=organization, name="Ana Comercial", email="ana@example.com")
    inactive_rep = SalesRep(organization=organization, name="Inativo", is_active=False)
    other_rep = SalesRep(organization=other_organization, name="Outro Vendedor")
    region = SalesRegion(
        organization=organization,
        name="Sao Paulo",
        region_type="mesoregion",
        state="SP",
        code="sp-sao-paulo",
        cities_json=["Sao Paulo", "Osasco"],
    )
    other_region = SalesRegion(
        organization=other_organization,
        name="Sao Paulo Other",
        region_type="mesoregion",
        state="SP",
        code="other-sp",
        cities_json=["Sao Paulo"],
    )
    segment = MarketSegment(
        organization=organization,
        key="varejo",
        name="Varejo",
        sort_order=10,
    )
    subsegment = MarketSubsegment(
        organization=organization,
        segment=segment,
        key="loja_de_tintas",
        name="loja de tintas",
        keywords_json=["loja de tintas", "tintas"],
        sort_order=10,
    )
    other_segment = MarketSegment(
        organization=other_organization,
        key="varejo",
        name="Varejo Other",
    )
    other_subsegment = MarketSubsegment(
        organization=other_organization,
        segment=other_segment,
        key="loja_de_tintas",
        name="loja de tintas other",
        keywords_json=["loja de tintas"],
    )
    inactive_rep_rule = AssignmentRule(
        organization=organization,
        name="Inactive rep should be skipped",
        priority=1,
        sales_region=region,
        market_segment=segment,
        market_subsegment=subsegment,
        sales_rep=inactive_rep,
    )
    rule = AssignmentRule(
        organization=organization,
        name="SP tintas",
        priority=5,
        sales_region=region,
        market_segment=segment,
        market_subsegment=subsegment,
        sales_rep=sales_rep,
        conditions_json={"ignored_for_now": True},
    )
    fallback_rule = AssignmentRule(
        organization=organization,
        name="Fallback",
        priority=50,
        sales_rep=sales_rep,
    )
    other_rule = AssignmentRule(
        organization=other_organization,
        name="Other tenant should be ignored",
        priority=0,
        sales_region=other_region,
        market_segment=other_segment,
        market_subsegment=other_subsegment,
        sales_rep=other_rep,
    )
    db_session.add_all(
        [
            organization,
            other_organization,
            inactive_rep_rule,
            rule,
            fallback_rule,
            other_rule,
        ]
    )
    db_session.flush()
    return {
        "organization": organization,
        "sales_rep": sales_rep,
        "inactive_rep": inactive_rep,
        "region": region,
        "segment": segment,
        "subsegment": subsegment,
        "rule": rule,
        "fallback_rule": fallback_rule,
    }


def test_lead_assignment_columns_and_indexes_are_created(session_factory) -> None:
    engine = session_factory.kw["bind"]
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("leads")}
    indexes = {index["name"] for index in inspector.get_indexes("leads")}

    assert {
        "sales_region_id",
        "market_segment_id",
        "market_subsegment_id",
        "assigned_sales_rep_id",
        "assignment_rule_id",
        "assignment_explanation",
        "assignment_metadata_json",
        "assigned_at",
    }.issubset(columns)
    assert {
        "ix_leads_org_sales_region",
        "ix_leads_org_market_segment",
        "ix_leads_org_market_subsegment",
        "ix_leads_org_assigned_sales_rep",
        "ix_leads_org_assignment_rule",
    }.issubset(indexes)


def test_assignment_service_matches_region_subsegment_and_priority_rule(db_session) -> None:
    fixture = _assignment_fixture(db_session)
    lead = _lead("Casa Alpha Tintas", organization=fixture["organization"], city="Sao Paulo", state="SP")
    db_session.add(lead)
    db_session.commit()

    result = LeadAssignmentService(db_session, organization_id=fixture["organization"].id).apply_to_lead(lead.id)
    db_session.refresh(lead)

    assert lead.sales_region == fixture["region"]
    assert lead.market_segment == fixture["segment"]
    assert lead.market_subsegment == fixture["subsegment"]
    assert lead.assigned_sales_rep == fixture["sales_rep"]
    assert lead.assignment_rule == fixture["rule"]
    assert lead.assigned_at is not None
    assert "assigned_sales_rep_id" in result.changed_fields
    assert "loja de tintas" in lead.assignment_metadata_json["market_subsegment"]["matched_keywords"]
    assert lead.assignment_metadata_json["assignment_rule"]["priority"] == 5
    assert set(lead.assignment_metadata_json) == {
        "schema_version",
        "sales_region",
        "market_segment",
        "market_subsegment",
        "assignment_rule",
        "sales_rep",
    }
    assert fixture["rule"].assigned_leads == [lead]
    assert fixture["sales_rep"].assigned_leads == [lead]
    assert fixture["region"].assigned_leads == [lead]
    assert fixture["segment"].classified_leads == [lead]
    assert fixture["subsegment"].classified_leads == [lead]


def test_assignment_service_ignores_cross_org_configuration(db_session) -> None:
    fixture = _assignment_fixture(db_session)
    lead = _lead("Casa Alpha Tintas", organization=fixture["organization"], city="Sao Paulo", state="SP")
    db_session.add(lead)
    db_session.commit()

    suggestion = LeadAssignmentService(db_session, organization_id=fixture["organization"].id).evaluate_lead(lead)

    assert suggestion.sales_region_id == fixture["region"].id
    assert suggestion.market_subsegment_id == fixture["subsegment"].id
    assert suggestion.assignment_rule_id == fixture["rule"].id
    assert suggestion.assigned_sales_rep_id == fixture["sales_rep"].id


def test_assignment_service_preserves_existing_assignment_when_overwrite_is_false(db_session) -> None:
    fixture = _assignment_fixture(db_session)
    manual_rep = SalesRep(organization=fixture["organization"], name="Manual Rep")
    lead = _lead("Casa Alpha Tintas", organization=fixture["organization"], city="Sao Paulo", state="SP")
    lead.assigned_sales_rep = manual_rep
    db_session.add_all([manual_rep, lead])
    db_session.commit()

    LeadAssignmentService(db_session, organization_id=fixture["organization"].id).apply_to_lead(
        lead.id,
        overwrite=False,
    )
    db_session.refresh(lead)

    assert lead.assigned_sales_rep == manual_rep
    assert lead.assignment_rule_id is None
    assert lead.sales_region == fixture["region"]
    assert lead.market_segment == fixture["segment"]
    assert lead.market_subsegment == fixture["subsegment"]


def test_assignment_service_can_overwrite_existing_assignment(db_session) -> None:
    fixture = _assignment_fixture(db_session)
    manual_rep = SalesRep(organization=fixture["organization"], name="Manual Rep")
    lead = _lead("Casa Alpha Tintas", organization=fixture["organization"], city="Sao Paulo", state="SP")
    lead.assigned_sales_rep = manual_rep
    db_session.add_all([manual_rep, lead])
    db_session.commit()

    LeadAssignmentService(db_session, organization_id=fixture["organization"].id).apply_to_lead(
        lead.id,
        overwrite=True,
    )
    db_session.refresh(lead)

    assert lead.assigned_sales_rep == fixture["sales_rep"]
    assert lead.assignment_rule == fixture["rule"]


def test_assignment_service_leaves_ids_null_when_no_match(db_session) -> None:
    organization = _organization("empty-tenant")
    lead = _lead(
        "Sem Classificacao",
        organization=organization,
        city="Ribeirao Preto",
        state="SP",
        category="categoria desconhecida",
    )
    db_session.add_all([organization, lead])
    db_session.commit()

    result = LeadAssignmentService(db_session, organization_id=organization.id).apply_to_lead(lead.id)
    db_session.refresh(lead)

    assert lead.sales_region_id is None
    assert lead.market_segment_id is None
    assert lead.market_subsegment_id is None
    assert lead.assigned_sales_rep_id is None
    assert lead.assignment_rule_id is None
    assert lead.assignment_metadata_json["sales_region"] is None
    assert lead.assignment_metadata_json["market_subsegment"] is None
    assert "No assignment rule matched" in (lead.assignment_explanation or "")
    assert result.suggestion.assigned_sales_rep_id is None
