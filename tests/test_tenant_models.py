from __future__ import annotations

from sqlalchemy import inspect

from app.models.assignment_rule import AssignmentRule
from app.models.market_taxonomy import MarketSegment, MarketSubsegment
from app.models.organization import Organization
from app.models.sales_region import SalesRegion
from app.models.sales_rep import SalesRep


def test_tenant_foundation_tables_are_created(session_factory) -> None:
    engine = session_factory.kw["bind"]
    table_names = set(inspect(engine).get_table_names())

    assert {
        "organizations",
        "sales_reps",
        "sales_regions",
        "market_segments",
        "market_subsegments",
        "assignment_rules",
    }.issubset(table_names)


def test_tenant_foundation_relationships_support_assignment_configuration(db_session) -> None:
    organization = Organization(
        slug="tenant-a",
        name="Tenant A",
        display_name="Tenant A",
        branding_json={"accent": "lavender"},
        terminology_json={"lead": "cliente potencial"},
    )
    sales_rep = SalesRep(
        organization=organization,
        name="Ana Comercial",
        email="ana@example.com",
        whatsapp="+5511999999999",
        external_ref="seller-ana",
    )
    sales_region = SalesRegion(
        organization=organization,
        name="Campinas",
        region_type="mesoregion",
        state="SP",
        code="sp-campinas",
        cities_json=["Campinas", "Americana", "Sumare"],
    )
    segment = MarketSegment(
        organization=organization,
        key="construcao_civil",
        name="Construção Civil",
        sort_order=30,
    )
    subsegment = MarketSubsegment(
        organization=organization,
        segment=segment,
        key="materiais_de_construcao",
        name="materiais de construção",
        keywords_json=["material de construção", "depósito de construção", "loja de construção"],
    )
    assignment_rule = AssignmentRule(
        organization=organization,
        name="Campinas construção civil",
        priority=10,
        sales_region=sales_region,
        market_segment=segment,
        market_subsegment=subsegment,
        sales_rep=sales_rep,
        conditions_json={"source": "default_assignment_bootstrap"},
    )

    db_session.add(organization)
    db_session.add(assignment_rule)
    db_session.commit()
    db_session.refresh(organization)
    db_session.refresh(segment)
    db_session.refresh(sales_rep)
    db_session.refresh(sales_region)

    assert organization.sales_reps == [sales_rep]
    assert organization.sales_regions == [sales_region]
    assert organization.market_segments == [segment]
    assert organization.assignment_rules == [assignment_rule]
    assert segment.subsegments == [subsegment]
    assert sales_rep.assignment_rules == [assignment_rule]
    assert sales_region.assignment_rules == [assignment_rule]
    assert assignment_rule.market_subsegment == subsegment
    assert subsegment.organization_id == organization.id
