from __future__ import annotations

from sqlalchemy import func, select

from app.enums import LeadSourceType, LeadStatus
from app.models.assignment_rule import AssignmentRule
from app.models.lead import Lead
from app.models.market_taxonomy import MarketSegment, MarketSubsegment
from app.models.sales_region import SalesRegion
from app.models.sales_rep import SalesRep
from app.repositories.lead_repository import LeadRepository
from app.schemas.lead import LeadListFilters, LeadSummary
from app.services.default_assignment_bootstrap import (
    DEFAULT_REGION_NAMES,
    DEFAULT_SALES_REP_NAMES,
    bootstrap_default_assignment_configuration,
)
from app.services.lead_assignment import LeadAssignmentService
from app.services.normalization import normalize_business_name


def _count(db_session, model) -> int:
    return db_session.execute(select(func.count(model.id))).scalar_one()


def _lead(
    business_name: str,
    *,
    organization_id: int,
    category: str,
    city: str,
    neighborhood: str | None = None,
    postal_code: str | None = None,
) -> Lead:
    return Lead(
        organization_id=organization_id,
        business_name=business_name,
        normalized_business_name=normalize_business_name(business_name) or business_name.lower(),
        category=category,
        city=city,
        state="SP",
        neighborhood=neighborhood,
        postal_code=postal_code,
        lead_source_type=LeadSourceType.GOOGLE_PLACES,
        status=LeadStatus.NEW,
    )


def test_default_assignment_bootstrap_seeds_reference_configuration_idempotently(db_session) -> None:
    result = bootstrap_default_assignment_configuration(db_session)
    first_counts = {
        "sales_reps": _count(db_session, SalesRep),
        "sales_regions": _count(db_session, SalesRegion),
        "market_segments": _count(db_session, MarketSegment),
        "market_subsegments": _count(db_session, MarketSubsegment),
        "assignment_rules": _count(db_session, AssignmentRule),
    }

    second_result = bootstrap_default_assignment_configuration(db_session)
    second_counts = {
        "sales_reps": _count(db_session, SalesRep),
        "sales_regions": _count(db_session, SalesRegion),
        "market_segments": _count(db_session, MarketSegment),
        "market_subsegments": _count(db_session, MarketSubsegment),
        "assignment_rules": _count(db_session, AssignmentRule),
    }

    rep_names = set(db_session.execute(select(SalesRep.name)).scalars().all())
    region_names = set(db_session.execute(select(SalesRegion.name)).scalars().all())

    assert result.organization_id == second_result.organization_id
    assert first_counts == second_counts
    assert set(DEFAULT_SALES_REP_NAMES).issubset(rep_names)
    assert set(DEFAULT_REGION_NAMES).issubset(region_names)
    assert result.sales_reps == len(DEFAULT_SALES_REP_NAMES)
    assert result.sales_regions == len(DEFAULT_REGION_NAMES)
    assert result.market_segments == 5
    assert result.market_subsegments >= 18
    assert result.assignment_rules == 66
    assert result.warnings
    assert "São José do Rio Preto" in result.warnings[0]


def test_default_assignment_routes_segments_regions_and_reps(db_session) -> None:
    result = bootstrap_default_assignment_configuration(db_session)
    leads = [
        _lead(
            "Construtora Beta",
            organization_id=result.organization_id,
            category="construtora",
            city="Campinas",
        ),
        _lead(
            "Química Alfa",
            organization_id=result.organization_id,
            category="indústria química",
            city="Bauru",
        ),
        _lead(
            "Ferragens Bauru",
            organization_id=result.organization_id,
            category="ferragista",
            city="Bauru",
        ),
        _lead(
            "Casa de Tintas Pinheiros",
            organization_id=result.organization_id,
            category="loja de tintas",
            city="São Paulo",
            neighborhood="Pinheiros",
        ),
        _lead(
            "Ferragens Rio Preto",
            organization_id=result.organization_id,
            category="ferragista",
            city="São José do Rio Preto",
        ),
    ]
    db_session.add_all(leads)
    db_session.flush()

    service = LeadAssignmentService(db_session, organization_id=result.organization_id)
    service.apply_batch(lead_ids=[lead.id for lead in leads])
    for lead in leads:
        db_session.refresh(lead)

    assert leads[0].sales_region.name == "Campinas"
    assert leads[0].market_segment.name == "Construção Civil"
    assert leads[0].assigned_sales_rep.name == "Construction Desk A"
    assert leads[1].market_segment.name == "Indústria"
    assert leads[1].assigned_sales_rep.name == "Industry Desk"
    assert leads[2].sales_region.name == "Bauru"
    assert leads[2].market_segment.name == "Varejo"
    assert leads[2].assigned_sales_rep.name == "Commercial Desk B"
    assert leads[3].sales_region.name == "São Paulo – Zona Oeste"
    assert leads[3].assigned_sales_rep.name == "Commercial Desk D"
    assert leads[4].sales_region.name == "São José do Rio Preto"
    assert leads[4].market_segment.name == "Varejo"
    assert leads[4].assigned_sales_rep_id is None


def test_assignment_does_not_guess_sao_paulo_zone_without_detail(db_session) -> None:
    result = bootstrap_default_assignment_configuration(db_session)
    lead = _lead(
        "Casa de Tintas São Paulo",
        organization_id=result.organization_id,
        category="loja de tintas",
        city="São Paulo",
    )
    db_session.add(lead)
    db_session.flush()

    LeadAssignmentService(db_session, organization_id=result.organization_id).apply_to_lead(lead.id)
    db_session.refresh(lead)

    assert lead.sales_region_id is None
    assert lead.market_segment.name == "Varejo"
    assert lead.assigned_sales_rep_id is None


def test_assignment_batch_dry_run_and_repository_assignment_filters(db_session) -> None:
    result = bootstrap_default_assignment_configuration(db_session)
    lead = _lead(
        "Casa de Tintas Pinheiros",
        organization_id=result.organization_id,
        category="loja de tintas",
        city="São Paulo",
        neighborhood="Pinheiros",
    )
    db_session.add(lead)
    db_session.flush()

    service = LeadAssignmentService(db_session, organization_id=result.organization_id)
    dry_run = service.apply_batch(lead_ids=[lead.id], dry_run=True)
    db_session.refresh(lead)

    assert dry_run.dry_run is True
    assert dry_run.changed == 1
    assert "assigned_sales_rep_id" in dry_run.results[0].changed_fields
    assert lead.assigned_sales_rep_id is None

    committed = service.apply_batch(lead_ids=[lead.id])
    db_session.refresh(lead)
    commercial_desk = db_session.execute(
        select(SalesRep).where(SalesRep.name == "Commercial Desk D")
    ).scalar_one()
    repository = LeadRepository(db_session, organization_id=result.organization_id)
    assigned_to_commercial_desk, total_assigned_to_commercial_desk = repository.list_leads(
        LeadListFilters(assigned_sales_rep_id=commercial_desk.id)
    )
    unassigned, total_unassigned = repository.list_leads(LeadListFilters(has_assignment=False))
    assignment_options = repository.list_assignment_filter_options()
    summary = LeadSummary.model_validate(assigned_to_commercial_desk[0])

    assert committed.dry_run is False
    assert lead.assigned_sales_rep == commercial_desk
    assert total_assigned_to_commercial_desk == 1
    assert assigned_to_commercial_desk[0].id == lead.id
    assert total_unassigned == 0
    assert unassigned == []
    assert (commercial_desk.id, "Commercial Desk D") in assignment_options["sales_reps"]
    assert (lead.sales_region.id, "São Paulo – Zona Oeste") in assignment_options["sales_regions"]
    assert summary.assigned_sales_rep and summary.assigned_sales_rep.name == "Commercial Desk D"
    assert summary.sales_region and summary.sales_region.name == "São Paulo – Zona Oeste"
