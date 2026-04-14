from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import json

import pandas as pd
from openpyxl.styles import Font, PatternFill
from openpyxl.formatting.rule import FormulaRule
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.app_setting import AppSetting
from app.models.outreach import OutreachDraft, OutreachMessage, OutreachTemplate
from app.repositories.lead_repository import LeadRepository
from app.repositories.settings_repository import SettingsRepository
from app.schemas.lead import LeadListFilters
from app.services.outreach import OutreachService


HEADER_FILL = PatternFill(fill_type="solid", fgColor="1F4E78")
HEADER_FONT = Font(color="FFFFFF", bold=True)
MISSING_FILL = PatternFill(fill_type="solid", fgColor="FCE4D6")
LEADS_COLUMNS = [
    "id",
    "business_name",
    "normalized_business_name",
    "category",
    "address",
    "neighborhood",
    "city",
    "state",
    "postal_code",
    "latitude",
    "longitude",
    "website",
    "domain",
    "email",
    "phone",
    "whatsapp",
    "instagram",
    "google_maps_url",
    "source_provider",
    "source_url",
    "lead_source_type",
    "sales_region",
    "market_segment",
    "market_subsegment",
    "assigned_sales_rep",
    "assignment_rule",
    "lead_score",
    "status",
    "notes",
    "follow_up_date",
    "assigned_at",
    "assignment_explanation",
    "do_not_contact",
    "is_duplicate",
    "duplicate_of_lead_id",
    "created_at",
    "updated_at",
    "last_contacted_at",
    "last_enriched_at",
]
OUTREACH_LOG_COLUMNS = [
    "record_type",
    "id",
    "lead_id",
    "channel",
    "template_key",
    "subject",
    "body",
    "status",
    "provider",
    "recipient",
    "created_at",
    "updated_at",
    "sent_at",
]
TEMPLATE_COLUMNS = [
    "id",
    "key",
    "channel",
    "name",
    "subject_template",
    "body_template",
    "is_active",
    "created_at",
    "updated_at",
]
SETTING_COLUMNS = ["id", "key", "value", "description", "created_at", "updated_at"]
METADATA_COLUMNS = ["metric", "value"]
SHEET_COLUMNS = {
    "Leads": LEADS_COLUMNS,
    "Outreach_Log": OUTREACH_LOG_COLUMNS,
    "Templates": TEMPLATE_COLUMNS,
    "Settings": SETTING_COLUMNS,
    "Metadata": METADATA_COLUMNS,
}


class ExcelExportService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.lead_repository = LeadRepository(db)
        self.settings_repository = SettingsRepository(db)
        self.outreach_service = OutreachService(db)

    def build_workbook(self, filters: LeadListFilters) -> tuple[str, bytes]:
        leads = self.lead_repository.list_all_leads(filters)
        lead_ids = [lead.id for lead in leads]

        templates = self.outreach_service.ensure_default_templates()
        settings_rows = self.settings_repository.list_settings()

        if lead_ids:
            draft_query = (
                select(OutreachDraft)
                .where(OutreachDraft.lead_id.in_(lead_ids))
                .order_by(OutreachDraft.created_at.desc())
            )
            message_query = (
                select(OutreachMessage)
                .where(OutreachMessage.lead_id.in_(lead_ids))
                .order_by(OutreachMessage.created_at.desc())
            )
            drafts = self.db.execute(draft_query).scalars().all()
            messages = self.db.execute(message_query).scalars().all()
        else:
            drafts = []
            messages = []

        leads_df = pd.DataFrame([self._lead_row(lead) for lead in leads])
        outreach_df = pd.DataFrame(
            [self._draft_row(draft) for draft in drafts]
            + [self._message_row(message) for message in messages]
        )
        templates_df = pd.DataFrame([self._template_row(template) for template in templates])
        settings_df = pd.DataFrame([self._setting_row(setting) for setting in settings_rows])
        metadata_df = pd.DataFrame(self._metadata_rows(leads_df, filters))

        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            self._write_sheet(writer, "Leads", leads_df)
            self._write_sheet(writer, "Outreach_Log", outreach_df)
            self._write_sheet(writer, "Templates", templates_df)
            self._write_sheet(writer, "Settings", settings_df)
            self._write_sheet(writer, "Metadata", metadata_df)

            workbook = writer.book
            self._format_sheet(workbook["Leads"], highlight_missing_contacts=True)
            self._format_sheet(workbook["Outreach_Log"])
            self._format_sheet(workbook["Templates"])
            self._format_sheet(workbook["Settings"])
            self._format_sheet(workbook["Metadata"], freeze_headers=False)

        filename = f"lead_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.xlsx"
        return filename, output.getvalue()

    def _write_sheet(self, writer: pd.ExcelWriter, sheet_name: str, dataframe: pd.DataFrame) -> None:
        frame = dataframe.copy()
        expected_columns = SHEET_COLUMNS.get(sheet_name)
        if expected_columns:
            frame = frame.reindex(columns=expected_columns)
        if frame.empty and expected_columns:
            frame = pd.DataFrame(columns=expected_columns)
        frame.to_excel(writer, sheet_name=sheet_name, index=False)

    def _format_sheet(self, worksheet, *, highlight_missing_contacts: bool = False, freeze_headers: bool = True) -> None:
        max_row = worksheet.max_row
        max_col = worksheet.max_column
        if max_row >= 1:
            for cell in worksheet[1]:
                cell.fill = HEADER_FILL
                cell.font = HEADER_FONT
            if freeze_headers:
                worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions

        for column_cells in worksheet.columns:
            values = [str(cell.value) if cell.value is not None else "" for cell in column_cells]
            max_length = max((len(value) for value in values), default=0)
            worksheet.column_dimensions[column_cells[0].column_letter].width = min(max_length + 2, 45)

        if highlight_missing_contacts and max_row > 1:
            headers = {worksheet.cell(row=1, column=index).value: index for index in range(1, max_col + 1)}
            for header_name in ["email", "phone", "whatsapp"]:
                column_index = headers.get(header_name)
                if not column_index:
                    continue
                column_letter = get_column_letter(column_index)
                worksheet.conditional_formatting.add(
                    f"{column_letter}2:{column_letter}{max_row}",
                    FormulaRule(
                        formula=[f'LEN(TRIM({column_letter}2))=0'],
                        fill=MISSING_FILL,
                    ),
                )

    @staticmethod
    def _lead_row(lead) -> dict[str, object]:
        return {
            "id": lead.id,
            "business_name": lead.business_name,
            "normalized_business_name": lead.normalized_business_name,
            "category": lead.category,
            "address": lead.address,
            "neighborhood": lead.neighborhood,
            "city": lead.city,
            "state": lead.state,
            "postal_code": lead.postal_code,
            "latitude": lead.latitude,
            "longitude": lead.longitude,
            "website": lead.website,
            "domain": lead.domain,
            "email": lead.email,
            "phone": lead.phone,
            "whatsapp": lead.whatsapp,
            "instagram": lead.instagram,
            "google_maps_url": lead.google_maps_url,
            "source_provider": lead.source_provider,
            "source_url": lead.source_url,
            "lead_source_type": lead.lead_source_type.value if lead.lead_source_type else None,
            "sales_region": lead.sales_region.name if lead.sales_region else None,
            "market_segment": lead.market_segment.name if lead.market_segment else None,
            "market_subsegment": lead.market_subsegment.name if lead.market_subsegment else None,
            "assigned_sales_rep": lead.assigned_sales_rep.name if lead.assigned_sales_rep else None,
            "assignment_rule": lead.assignment_rule.name if lead.assignment_rule else None,
            "lead_score": lead.lead_score,
            "status": lead.status.value if lead.status else None,
            "notes": lead.notes,
            "follow_up_date": lead.follow_up_date,
            "assigned_at": lead.assigned_at,
            "assignment_explanation": lead.assignment_explanation,
            "do_not_contact": lead.do_not_contact,
            "is_duplicate": lead.is_duplicate,
            "duplicate_of_lead_id": lead.duplicate_of_lead_id,
            "created_at": lead.created_at,
            "updated_at": lead.updated_at,
            "last_contacted_at": lead.last_contacted_at,
            "last_enriched_at": lead.last_enriched_at,
        }

    @staticmethod
    def _draft_row(draft: OutreachDraft) -> dict[str, object]:
        return {
            "record_type": "draft",
            "id": draft.id,
            "lead_id": draft.lead_id,
            "channel": draft.channel.value if draft.channel else None,
            "template_key": draft.draft_type.value if draft.draft_type else None,
            "subject": draft.subject,
            "body": draft.body,
            "status": draft.status.value if draft.status else None,
            "provider": None,
            "recipient": None,
            "created_at": draft.created_at,
            "updated_at": draft.updated_at,
            "sent_at": None,
        }

    @staticmethod
    def _message_row(message: OutreachMessage) -> dict[str, object]:
        return {
            "record_type": "message",
            "id": message.id,
            "lead_id": message.lead_id,
            "channel": message.channel.value if message.channel else None,
            "template_key": None,
            "subject": message.subject,
            "body": message.body,
            "status": message.status.value if message.status else None,
            "provider": message.provider,
            "recipient": message.recipient,
            "created_at": message.created_at,
            "updated_at": message.updated_at,
            "sent_at": message.sent_at,
        }

    @staticmethod
    def _template_row(template: OutreachTemplate) -> dict[str, object]:
        return {
            "id": template.id,
            "key": template.key.value if template.key else None,
            "channel": template.channel.value if template.channel else None,
            "name": template.name,
            "subject_template": template.subject_template,
            "body_template": template.body_template,
            "is_active": template.is_active,
            "created_at": template.created_at,
            "updated_at": template.updated_at,
        }

    @staticmethod
    def _setting_row(setting: AppSetting) -> dict[str, object]:
        return {
            "id": setting.id,
            "key": setting.key,
            "value": json.dumps(setting.value, ensure_ascii=True),
            "description": setting.description,
            "created_at": setting.created_at,
            "updated_at": setting.updated_at,
        }

    @staticmethod
    def _metadata_rows(leads_df: pd.DataFrame, filters: LeadListFilters) -> list[dict[str, object]]:
        duplicate_count = int(leads_df["is_duplicate"].sum()) if not leads_df.empty else 0
        total_with_email = int(leads_df["email"].fillna("").astype(str).str.len().gt(0).sum()) if not leads_df.empty else 0
        total_with_whatsapp = int(leads_df["whatsapp"].fillna("").astype(str).str.len().gt(0).sum()) if not leads_df.empty else 0
        total_with_website = int(leads_df["website"].fillna("").astype(str).str.len().gt(0).sum()) if not leads_df.empty else 0
        score_min = int(leads_df["lead_score"].min()) if not leads_df.empty else 0
        score_avg = float(leads_df["lead_score"].mean()) if not leads_df.empty else 0.0
        score_max = int(leads_df["lead_score"].max()) if not leads_df.empty else 0

        return [
            {"metric": "export_timestamp_utc", "value": datetime.now(timezone.utc).isoformat()},
            {"metric": "applied_filters", "value": json.dumps(filters.model_dump(mode="json"), ensure_ascii=True)},
            {"metric": "total_lead_count", "value": int(len(leads_df.index))},
            {"metric": "total_duplicate_count", "value": duplicate_count},
            {"metric": "total_with_email", "value": total_with_email},
            {"metric": "total_with_whatsapp", "value": total_with_whatsapp},
            {"metric": "total_with_website", "value": total_with_website},
            {"metric": "score_min", "value": score_min},
            {"metric": "score_avg", "value": round(score_avg, 2)},
            {"metric": "score_max", "value": score_max},
        ]
