from __future__ import annotations

from io import BytesIO

from openpyxl import load_workbook

from app.enums import LeadSourceType, LeadStatus
from app.models.app_setting import AppSetting
from app.models.assignment_rule import AssignmentRule
from app.models.lead import Lead
from app.models.market_taxonomy import MarketSegment, MarketSubsegment
from app.models.organization import Organization
from app.models.sales_region import SalesRegion
from app.models.sales_rep import SalesRep
from app.schemas.lead import LeadListFilters
from app.services.export_excel import ExcelExportService
from app.services.normalization import normalize_business_name
from app.services.outreach import OutreachService


def test_excel_export_contains_required_sheets(db_session) -> None:
    organization = Organization(slug="garin", name="Garin", display_name="Garin")
    region = SalesRegion(
        organization=organization,
        name="Campinas",
        region_type="mesoregion",
        state="SP",
        code="sp-campinas",
    )
    segment = MarketSegment(organization=organization, key="varejo", name="Varejo")
    subsegment = MarketSubsegment(
        organization=organization,
        segment=segment,
        key="loja_de_tintas",
        name="loja de tintas",
    )
    sales_rep = SalesRep(organization=organization, name="Vendas2")
    rule = AssignmentRule(
        organization=organization,
        name="Varejo - Vendas2 - Campinas",
        sales_region=region,
        market_segment=segment,
        sales_rep=sales_rep,
    )
    lead = Lead(
        organization=organization,
        business_name="Oficina Export",
        normalized_business_name=normalize_business_name("Oficina Export") or "oficina export",
        category="oficina mecanica",
        city="Sao Paulo",
        state="SP",
        website="https://export.com.br",
        email="contato@export.com.br",
        whatsapp="+5511999999999",
        lead_source_type=LeadSourceType.GOOGLE_PLACES,
        status=LeadStatus.NEW,
        sales_region=region,
        market_segment=segment,
        market_subsegment=subsegment,
        assigned_sales_rep=sales_rep,
        assignment_rule=rule,
        assignment_explanation="Matched test assignment.",
    )
    db_session.add(lead)
    db_session.add(AppSetting(key="daily_email_limit", value={"value": 25}, description="Daily email limit"))
    db_session.commit()
    db_session.refresh(lead)

    OutreachService(db_session).list_templates()

    service = ExcelExportService(db_session)
    filename, payload = service.build_workbook(LeadListFilters())

    workbook = load_workbook(BytesIO(payload))

    assert filename.endswith(".xlsx")
    assert payload[:2] == b"PK"
    assert "Leads" in workbook.sheetnames
    assert "Outreach_Log" in workbook.sheetnames
    assert "Templates" in workbook.sheetnames
    assert "Settings" in workbook.sheetnames
    assert "Metadata" in workbook.sheetnames
    metadata_rows = [row[0].value for row in workbook["Metadata"].iter_rows(min_row=2, max_col=1)]
    lead_headers = [cell.value for cell in workbook["Leads"][1]]
    assert "export_timestamp_utc" in metadata_rows
    assert "sales_region" in lead_headers
    assert "market_segment" in lead_headers
    assert "market_subsegment" in lead_headers
    assert "assigned_sales_rep" in lead_headers
    assert "assignment_rule" in lead_headers
    assert "assigned_at" in lead_headers
    assert "assignment_explanation" in lead_headers
