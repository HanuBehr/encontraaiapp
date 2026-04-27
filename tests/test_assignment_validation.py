from __future__ import annotations

import json
import shutil
from pathlib import Path

from app.enums import LeadSourceType, LeadStatus
from app.models.lead import Lead
from app.services.default_assignment_bootstrap import bootstrap_default_assignment_configuration
from app.services.lead_assignment_validation import AssignmentValidationService
from app.services.normalization import normalize_business_name


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


def test_validation_defaults_to_org_that_owns_current_leads_and_writes_artifacts(db_session) -> None:
    bootstrap_default_assignment_configuration(db_session, organization_slug="tenant-a")
    default_result = bootstrap_default_assignment_configuration(db_session)
    lead = _lead(
        "Construtora Campinas",
        organization_id=default_result.organization_id,
        category="construtora",
        city="Campinas",
    )
    db_session.add(lead)
    db_session.flush()

    service = AssignmentValidationService(db_session)
    report = service.build_report(dry_run=True)
    output_dir = Path(".pytest_cache") / "assignment_validation_test"
    if output_dir.exists():
        shutil.rmtree(output_dir, ignore_errors=True)
    artifacts = service.write_artifacts(report, output_dir)
    summary = json.loads(artifacts.summary_json.read_text(encoding="utf-8"))

    assert report.organization_slug == "default"
    assert report.organization_source == "lead_owner_default_plus_legacy_null"
    assert report.processed == 1
    assert report.assigned_count == 1
    assert report.counts_by_rep == {"Construction Desk A": 1}
    assert report.counts_by_region == {"Campinas": 1}
    assert report.counts_by_segment == {"Construção Civil": 1}
    assert report.counts_by_subsegment == {"construtoras": 1}
    assert summary["assigned_count"] == 1
    assert artifacts.assigned_csv.exists()
    assert artifacts.unassigned_csv.exists()
    assert artifacts.suspicious_matches_csv.exists()
    shutil.rmtree(output_dir, ignore_errors=True)


def test_validation_reports_assignment_counts_by_rep_region_and_segment(db_session) -> None:
    result = bootstrap_default_assignment_configuration(db_session)
    leads = [
        _lead(
            "Construtora Campinas",
            organization_id=result.organization_id,
            category="construtora",
            city="Campinas",
        ),
        _lead(
            "Ferragens Bauru",
            organization_id=result.organization_id,
            category="ferragista",
            city="Bauru",
        ),
        _lead(
            "Química Bauru",
            organization_id=result.organization_id,
            category="indústria química",
            city="Bauru",
        ),
    ]
    db_session.add_all(leads)
    db_session.flush()

    report = AssignmentValidationService(db_session).build_report(dry_run=True)

    assert report.processed == 3
    assert report.assigned_count == 3
    assert report.unassigned_count == 0
    assert report.counts_by_rep == {
        "Commercial Desk B": 1,
        "Construction Desk A": 1,
        "Industry Desk": 1,
    }
    assert report.counts_by_region == {"Bauru": 2, "Campinas": 1}
    assert report.counts_by_segment == {"Construção Civil": 1, "Indústria": 1, "Varejo": 1}


def test_validation_reports_unassigned_reason_buckets(db_session) -> None:
    result = bootstrap_default_assignment_configuration(db_session)
    leads = [
        _lead(
            "Casa de Tintas São Paulo",
            organization_id=result.organization_id,
            category="loja de tintas",
            city="São Paulo",
        ),
        _lead(
            "Comércio Sem Categoria",
            organization_id=result.organization_id,
            category="categoria desconhecida",
            city="Campinas",
        ),
        _lead(
            "Loja de Tintas Sem Região",
            organization_id=result.organization_id,
            category="loja de tintas",
            city="Cidade Sem Região",
        ),
    ]
    db_session.add_all(leads)
    db_session.flush()

    report = AssignmentValidationService(db_session).build_report(dry_run=True)

    assert report.assigned_count == 0
    assert report.unassigned_reasons == {
        "no_market_subsegment_matched": 1,
        "no_sales_region_matched": 1,
        "sao_paulo_missing_zone_signal": 1,
    }


def test_validation_marks_sao_jose_do_rio_preto_commercial_gap_as_expected(db_session) -> None:
    result = bootstrap_default_assignment_configuration(db_session)
    lead = _lead(
        "Ferragens Rio Preto",
        organization_id=result.organization_id,
        category="ferragista",
        city="São José do Rio Preto",
    )
    db_session.add(lead)
    db_session.flush()

    report = AssignmentValidationService(db_session).build_report(dry_run=True)

    assert report.assigned_count == 0
    assert report.expected_sjrp_gap_count == 1
    assert report.unexpected_sjrp_gap_count == 0
    assert report.unassigned_reasons == {"expected_sao_jose_do_rio_preto_commercial_gap": 1}


def test_validation_reports_suspicious_broad_subsegment_matches(db_session) -> None:
    result = bootstrap_default_assignment_configuration(db_session)
    lead = _lead(
        "Marketplace Obra",
        organization_id=result.organization_id,
        category="marketplace",
        city="Campinas",
    )
    db_session.add(lead)
    db_session.flush()

    report = AssignmentValidationService(db_session).build_report(dry_run=True)
    suspicious_rows = [row for row in report.rows if row.suspicious_reasons]

    assert report.assigned_count == 1
    assert report.suspicious_match_count == 1
    assert suspicious_rows[0].business_name == "Marketplace Obra"
    assert "broad_keyword:marketplace" in suspicious_rows[0].suspicious_reasons


def test_validation_dry_run_does_not_mutate_leads(db_session) -> None:
    result = bootstrap_default_assignment_configuration(db_session)
    lead = _lead(
        "Construtora Campinas",
        organization_id=result.organization_id,
        category="construtora",
        city="Campinas",
    )
    db_session.add(lead)
    db_session.flush()

    report = AssignmentValidationService(db_session).build_report(dry_run=True)
    db_session.refresh(lead)

    assert report.assigned_count == 1
    assert report.changed == 1
    assert lead.assigned_sales_rep_id is None
    assert lead.sales_region_id is None
    assert lead.market_segment_id is None
