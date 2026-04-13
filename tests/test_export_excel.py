from __future__ import annotations

from io import BytesIO

from openpyxl import load_workbook

from app.enums import LeadSourceType, LeadStatus
from app.models.app_setting import AppSetting
from app.models.lead import Lead
from app.schemas.lead import LeadListFilters
from app.services.export_excel import ExcelExportService
from app.services.normalization import normalize_business_name
from app.services.outreach import OutreachService


def test_excel_export_contains_required_sheets(db_session) -> None:
    lead = Lead(
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
    assert "export_timestamp_utc" in metadata_rows
