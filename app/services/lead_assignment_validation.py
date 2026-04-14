from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.assignment_rule import AssignmentRule
from app.models.lead import Lead
from app.models.market_taxonomy import MarketSegment, MarketSubsegment
from app.models.organization import Organization
from app.models.sales_region import SalesRegion
from app.models.sales_rep import SalesRep
from app.repositories.lead_repository import LeadRepository
from app.repositories.organization_repository import (
    DEFAULT_ORGANIZATION_SLUG,
    OrganizationRepository,
    get_or_create_default_organization,
)
from app.services.garin_bootstrap import bootstrap_garin_configuration
from app.services.lead_assignment import LeadAssignmentService, LeadAssignmentSuggestion
from app.services.normalization import normalize_text


COMMERCIAL_SEGMENT_KEYS = {"varejo", "atacado_distribuidora", "e_commerce"}
SAO_JOSE_DO_RIO_PRETO = "sao jose do rio preto"
BROAD_MATCH_KEYWORDS = {
    "marketplace",
    "loja virtual",
    "e commerce",
    "ecommerce",
    "marmore",
    "granito",
    "refrigeracao",
    "climatizacao",
    "ar condicionado",
}


@dataclass(slots=True)
class ValidationArtifacts:
    summary_json: Path
    assigned_csv: Path
    unassigned_csv: Path
    suspicious_matches_csv: Path


@dataclass(slots=True)
class OrganizationScope:
    organization: Organization
    repository_organization_id: int | None
    source: str
    lead_count: int
    legacy_null_lead_count: int = 0


@dataclass(slots=True)
class ValidationLeadRow:
    lead_id: int
    business_name: str
    city: str | None
    neighborhood: str | None
    postal_code: str | None
    category: str | None
    assigned_sales_rep: str | None
    sales_region: str | None
    market_segment: str | None
    market_segment_key: str | None
    market_subsegment: str | None
    assignment_rule: str | None
    matched_keywords: list[str] = field(default_factory=list)
    unassigned_reason: str | None = None
    suspicious_reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ValidationReport:
    mode: str
    organization_id: int
    organization_slug: str
    organization_source: str
    processed: int
    changed: int
    assigned_count: int
    unassigned_count: int
    assignment_rate: float
    counts_by_rep: dict[str, int]
    counts_by_region: dict[str, int]
    counts_by_segment: dict[str, int]
    counts_by_subsegment: dict[str, int]
    unassigned_reasons: dict[str, int]
    expected_sjrp_gap_count: int
    unexpected_sjrp_gap_count: int
    suspicious_match_count: int
    rows: list[ValidationLeadRow]
    bootstrap_warnings: list[str] = field(default_factory=list)
    artifacts: ValidationArtifacts | None = None

    def to_summary_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "organization": {
                "id": self.organization_id,
                "slug": self.organization_slug,
                "source": self.organization_source,
            },
            "processed": self.processed,
            "changed": self.changed,
            "assigned_count": self.assigned_count,
            "unassigned_count": self.unassigned_count,
            "assignment_rate": self.assignment_rate,
            "counts_by_rep": self.counts_by_rep,
            "counts_by_region": self.counts_by_region,
            "counts_by_segment": self.counts_by_segment,
            "counts_by_subsegment": self.counts_by_subsegment,
            "unassigned_reasons": self.unassigned_reasons,
            "checks": {
                "expected_sao_jose_do_rio_preto_gap_count": self.expected_sjrp_gap_count,
                "unexpected_sao_jose_do_rio_preto_gap_count": self.unexpected_sjrp_gap_count,
                "suspicious_match_count": self.suspicious_match_count,
            },
            "bootstrap_warnings": self.bootstrap_warnings,
            "artifacts": (
                {
                    "summary_json": str(self.artifacts.summary_json),
                    "assigned_csv": str(self.artifacts.assigned_csv),
                    "unassigned_csv": str(self.artifacts.unassigned_csv),
                    "suspicious_matches_csv": str(self.artifacts.suspicious_matches_csv),
                }
                if self.artifacts
                else None
            ),
        }


class GarinAssignmentValidationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def resolve_organization_scope(self, organization_slug: str | None = None) -> OrganizationScope:
        if organization_slug:
            organization = OrganizationRepository(self.db).get_by_slug(organization_slug)
            if organization is None:
                raise ValueError(f"Organization slug '{organization_slug}' was not found.")
            lead_count = self._lead_count_for_org(organization.id)
            return OrganizationScope(
                organization=organization,
                repository_organization_id=organization.id,
                source="explicit_slug",
                lead_count=lead_count,
            )

        lead_counts = self.db.execute(
            select(Lead.organization_id, func.count(Lead.id))
            .group_by(Lead.organization_id)
            .order_by(func.count(Lead.id).desc())
        ).all()
        non_null_counts = [(organization_id, count) for organization_id, count in lead_counts if organization_id is not None]
        null_count = next((count for organization_id, count in lead_counts if organization_id is None), 0)

        if non_null_counts:
            organization_id, lead_count = non_null_counts[0]
            organization = self.db.get(Organization, organization_id)
            if organization is None:
                organization = get_or_create_default_organization(self.db)
                return OrganizationScope(
                    organization=organization,
                    repository_organization_id=None,
                    source="default_fallback_for_missing_org",
                    lead_count=int(null_count),
                    legacy_null_lead_count=int(null_count),
                )

            if organization.slug == DEFAULT_ORGANIZATION_SLUG:
                return OrganizationScope(
                    organization=organization,
                    repository_organization_id=None,
                    source="lead_owner_default_plus_legacy_null",
                    lead_count=int(lead_count + null_count),
                    legacy_null_lead_count=int(null_count),
                )

            return OrganizationScope(
                organization=organization,
                repository_organization_id=organization.id,
                source="lead_owner_majority",
                lead_count=int(lead_count),
                legacy_null_lead_count=int(null_count),
            )

        organization = get_or_create_default_organization(self.db)
        return OrganizationScope(
            organization=organization,
            repository_organization_id=None,
            source="default_no_owned_leads" if not null_count else "legacy_null_leads_default",
            lead_count=int(null_count),
            legacy_null_lead_count=int(null_count),
        )

    def build_report(
        self,
        *,
        organization_slug: str | None = None,
        dry_run: bool = False,
        overwrite: bool = False,
        bootstrap: bool = False,
    ) -> ValidationReport:
        scope = self.resolve_organization_scope(organization_slug)
        bootstrap_warnings: list[str] = []
        if bootstrap:
            bootstrap_result = bootstrap_garin_configuration(self.db, organization_slug=scope.organization.slug)
            self.db.commit()
            bootstrap_warnings = list(bootstrap_result.warnings)
            scope = self.resolve_organization_scope(scope.organization.slug)

        repository = LeadRepository(self.db, organization_id=scope.repository_organization_id)
        leads = repository.list_all_leads()
        assignment_service = LeadAssignmentService(self.db, organization_id=scope.repository_organization_id)
        dry_run_results_by_id = {}
        if dry_run:
            batch_result = assignment_service.apply_batch(
                lead_ids=[lead.id for lead in leads],
                overwrite=overwrite,
                dry_run=True,
            )
            dry_run_results_by_id = {result.lead_id: result for result in batch_result.results}
            changed = batch_result.changed
        else:
            changed = 0

        labels = self._labels_by_id()
        rows = [
            self._build_row(
                lead,
                assignment_service=assignment_service,
                labels=labels,
                dry_run=dry_run,
                overwrite=overwrite,
                dry_run_suggestion=(
                    dry_run_results_by_id[lead.id].suggestion
                    if lead.id in dry_run_results_by_id
                    else None
                ),
            )
            for lead in leads
        ]

        assigned_rows = [row for row in rows if row.assigned_sales_rep]
        unassigned_rows = [row for row in rows if not row.assigned_sales_rep]
        suspicious_rows = [row for row in rows if row.suspicious_reasons]

        return ValidationReport(
            mode="dry-run" if dry_run else "current",
            organization_id=scope.organization.id,
            organization_slug=scope.organization.slug,
            organization_source=scope.source,
            processed=len(rows),
            changed=changed,
            assigned_count=len(assigned_rows),
            unassigned_count=len(unassigned_rows),
            assignment_rate=round((len(assigned_rows) / len(rows)) * 100, 2) if rows else 0.0,
            counts_by_rep=dict(sorted(Counter(row.assigned_sales_rep for row in assigned_rows).items())),
            counts_by_region=dict(sorted(Counter(row.sales_region or "Unmatched" for row in rows).items())),
            counts_by_segment=dict(sorted(Counter(row.market_segment or "Unclassified" for row in rows).items())),
            counts_by_subsegment=dict(sorted(Counter(row.market_subsegment or "Unclassified" for row in rows).items())),
            unassigned_reasons=dict(sorted(Counter(row.unassigned_reason for row in unassigned_rows).items())),
            expected_sjrp_gap_count=sum(
                1 for row in unassigned_rows if row.unassigned_reason == "expected_sao_jose_do_rio_preto_commercial_gap"
            ),
            unexpected_sjrp_gap_count=sum(1 for row in unassigned_rows if self._is_unexpected_sjrp_gap(row)),
            suspicious_match_count=len(suspicious_rows),
            rows=rows,
            bootstrap_warnings=bootstrap_warnings,
        )

    def write_artifacts(self, report: ValidationReport, output_dir: Path) -> ValidationArtifacts:
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        prefix = output_dir / f"garin_assignment_validation_{timestamp}"

        artifacts = ValidationArtifacts(
            summary_json=prefix.with_suffix(".json"),
            assigned_csv=output_dir / f"garin_assignment_assigned_{timestamp}.csv",
            unassigned_csv=output_dir / f"garin_assignment_unassigned_{timestamp}.csv",
            suspicious_matches_csv=output_dir / f"garin_assignment_suspicious_matches_{timestamp}.csv",
        )
        report.artifacts = artifacts

        artifacts.summary_json.write_text(
            json.dumps(report.to_summary_dict(), ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        self._write_rows_csv(
            artifacts.assigned_csv,
            [row for row in report.rows if row.assigned_sales_rep],
        )
        self._write_rows_csv(
            artifacts.unassigned_csv,
            [row for row in report.rows if not row.assigned_sales_rep],
        )
        self._write_rows_csv(
            artifacts.suspicious_matches_csv,
            [row for row in report.rows if row.suspicious_reasons],
        )
        return artifacts

    def console_summary(self, report: ValidationReport) -> str:
        top_reasons = self._format_counter(report.unassigned_reasons, empty="none")
        top_reps = self._format_counter(report.counts_by_rep, empty="none")
        top_regions = self._format_counter(report.counts_by_region, empty="none")
        lines = [
            f"Garin assignment validation ({report.mode})",
            f"Organization: {report.organization_slug} (id={report.organization_id}, source={report.organization_source})",
            (
                f"Leads: {report.processed} | assigned: {report.assigned_count} "
                f"({report.assignment_rate:.2f}%) | unassigned: {report.unassigned_count}"
            ),
        ]
        if report.mode == "dry-run":
            lines.append(f"Would change: {report.changed}")
        lines.extend(
            [
                f"By rep: {top_reps}",
                f"By region: {top_regions}",
                f"Top unassigned reasons: {top_reasons}",
                (
                    "Checks: "
                    f"SJRP expected gaps={report.expected_sjrp_gap_count}, "
                    f"SJRP unexpected gaps={report.unexpected_sjrp_gap_count}, "
                    f"suspicious matches={report.suspicious_match_count}"
                ),
            ]
        )
        if report.bootstrap_warnings:
            lines.extend(f"Bootstrap warning: {warning}" for warning in report.bootstrap_warnings)
        if report.artifacts:
            lines.extend(
                [
                    "Artifacts:",
                    f"- {report.artifacts.summary_json}",
                    f"- {report.artifacts.assigned_csv}",
                    f"- {report.artifacts.unassigned_csv}",
                    f"- {report.artifacts.suspicious_matches_csv}",
                ]
            )
        return "\n".join(lines)

    def _build_row(
        self,
        lead: Lead,
        *,
        assignment_service: LeadAssignmentService,
        labels: dict[str, dict[int, str]],
        dry_run: bool,
        overwrite: bool,
        dry_run_suggestion: LeadAssignmentSuggestion | None,
    ) -> ValidationLeadRow:
        suggestion = dry_run_suggestion or assignment_service.evaluate_lead(lead)
        effective = self._effective_assignment_values(lead, suggestion, dry_run=dry_run, overwrite=overwrite)
        matched_keywords = self._matched_keywords(lead, suggestion=suggestion)
        row = ValidationLeadRow(
            lead_id=lead.id,
            business_name=lead.business_name,
            city=lead.city,
            neighborhood=lead.neighborhood,
            postal_code=lead.postal_code,
            category=lead.category,
            assigned_sales_rep=self._label(labels["sales_reps"], effective["assigned_sales_rep_id"]),
            sales_region=self._label(labels["sales_regions"], effective["sales_region_id"]),
            market_segment=self._label(labels["market_segments"], effective["market_segment_id"]),
            market_segment_key=self._segment_key(effective["market_segment_id"]),
            market_subsegment=self._label(labels["market_subsegments"], effective["market_subsegment_id"]),
            assignment_rule=self._label(labels["assignment_rules"], effective["assignment_rule_id"]),
            matched_keywords=matched_keywords,
        )
        row.suspicious_reasons = self._suspicious_reasons(row)
        if not row.assigned_sales_rep:
            row.unassigned_reason = self._unassigned_reason(lead, row=row, suggestion=suggestion, dry_run=dry_run)
        return row

    @staticmethod
    def _effective_assignment_values(
        lead: Lead,
        suggestion: LeadAssignmentSuggestion,
        *,
        dry_run: bool,
        overwrite: bool,
    ) -> dict[str, int | None]:
        if not dry_run:
            return {
                "sales_region_id": lead.sales_region_id,
                "market_segment_id": lead.market_segment_id,
                "market_subsegment_id": lead.market_subsegment_id,
                "assigned_sales_rep_id": lead.assigned_sales_rep_id,
                "assignment_rule_id": lead.assignment_rule_id,
            }
        if overwrite:
            return {
                "sales_region_id": suggestion.sales_region_id,
                "market_segment_id": suggestion.market_segment_id,
                "market_subsegment_id": suggestion.market_subsegment_id,
                "assigned_sales_rep_id": suggestion.assigned_sales_rep_id,
                "assignment_rule_id": suggestion.assignment_rule_id,
            }
        return {
            "sales_region_id": lead.sales_region_id or suggestion.sales_region_id,
            "market_segment_id": lead.market_segment_id or suggestion.market_segment_id,
            "market_subsegment_id": lead.market_subsegment_id or suggestion.market_subsegment_id,
            "assigned_sales_rep_id": lead.assigned_sales_rep_id or suggestion.assigned_sales_rep_id,
            "assignment_rule_id": (
                lead.assignment_rule_id
                if lead.assigned_sales_rep_id
                else lead.assignment_rule_id or suggestion.assignment_rule_id
            ),
        }

    def _unassigned_reason(
        self,
        lead: Lead,
        *,
        row: ValidationLeadRow,
        suggestion: LeadAssignmentSuggestion,
        dry_run: bool,
    ) -> str:
        if not dry_run and suggestion.assigned_sales_rep_id:
            return "assignment_available_not_committed"
        if self._is_expected_sjrp_gap(row):
            return "expected_sao_jose_do_rio_preto_commercial_gap"
        if not row.sales_region:
            if normalize_text(lead.city) == "sao paulo":
                return "sao_paulo_missing_zone_signal"
            return "no_sales_region_matched"
        if not row.market_subsegment:
            return "no_market_subsegment_matched"
        if row.market_segment and not row.assignment_rule:
            return "no_assignment_rule_matched"
        return "unassigned_unknown"

    @staticmethod
    def _is_expected_sjrp_gap(row: ValidationLeadRow) -> bool:
        return normalize_text(row.sales_region) == SAO_JOSE_DO_RIO_PRETO and row.market_segment_key in COMMERCIAL_SEGMENT_KEYS

    @staticmethod
    def _is_unexpected_sjrp_gap(row: ValidationLeadRow) -> bool:
        return normalize_text(row.sales_region) == SAO_JOSE_DO_RIO_PRETO and row.market_segment_key not in COMMERCIAL_SEGMENT_KEYS

    @staticmethod
    def _matched_keywords(lead: Lead, *, suggestion: LeadAssignmentSuggestion) -> list[str]:
        metadata = suggestion.metadata or lead.assignment_metadata_json or {}
        subsegment_payload = metadata.get("market_subsegment") or {}
        return [str(keyword) for keyword in subsegment_payload.get("matched_keywords", []) if keyword]

    @staticmethod
    def _suspicious_reasons(row: ValidationLeadRow) -> list[str]:
        reasons: list[str] = []
        normalized_keywords = {normalize_text(keyword) for keyword in row.matched_keywords}
        broad_matches = sorted(keyword for keyword in normalized_keywords if keyword in BROAD_MATCH_KEYWORDS)
        if broad_matches:
            reasons.append("broad_keyword:" + "|".join(broad_matches))
        if len(row.matched_keywords) == 1 and row.market_subsegment in {"marketplace / loja virtual", "refrigeração"}:
            reasons.append("single_keyword_broad_subsegment")
        return reasons

    def _labels_by_id(self) -> dict[str, dict[int, str]]:
        return {
            "sales_reps": self._label_map(SalesRep),
            "sales_regions": self._label_map(SalesRegion),
            "market_segments": self._label_map(MarketSegment),
            "market_subsegments": self._label_map(MarketSubsegment),
            "assignment_rules": self._label_map(AssignmentRule),
        }

    def _label_map(self, model) -> dict[int, str]:
        return {
            int(row.id): str(row.name)
            for row in self.db.execute(select(model.id, model.name)).all()
        }

    def _segment_key(self, segment_id: int | None) -> str | None:
        if segment_id is None:
            return None
        return self.db.execute(select(MarketSegment.key).where(MarketSegment.id == segment_id)).scalar_one_or_none()

    @staticmethod
    def _label(labels: dict[int, str], item_id: int | None) -> str | None:
        if item_id is None:
            return None
        return labels.get(item_id, f"id:{item_id}")

    def _lead_count_for_org(self, organization_id: int) -> int:
        return int(
            self.db.execute(
                select(func.count(Lead.id)).where(Lead.organization_id == organization_id)
            ).scalar_one()
        )

    @staticmethod
    def _format_counter(values: dict[str, int], *, empty: str) -> str:
        if not values:
            return empty
        top_items = sorted(values.items(), key=lambda item: (-item[1], item[0]))[:5]
        return ", ".join(f"{key}={value}" for key, value in top_items)

    @staticmethod
    def _write_rows_csv(path: Path, rows: list[ValidationLeadRow]) -> None:
        fieldnames = [
            "lead_id",
            "business_name",
            "city",
            "neighborhood",
            "postal_code",
            "category",
            "assigned_sales_rep",
            "sales_region",
            "market_segment",
            "market_subsegment",
            "assignment_rule",
            "matched_keywords",
            "unassigned_reason",
            "suspicious_reasons",
        ]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "lead_id": row.lead_id,
                        "business_name": row.business_name,
                        "city": row.city,
                        "neighborhood": row.neighborhood,
                        "postal_code": row.postal_code,
                        "category": row.category,
                        "assigned_sales_rep": row.assigned_sales_rep,
                        "sales_region": row.sales_region,
                        "market_segment": row.market_segment,
                        "market_subsegment": row.market_subsegment,
                        "assignment_rule": row.assignment_rule,
                        "matched_keywords": "|".join(row.matched_keywords),
                        "unassigned_reason": row.unassigned_reason,
                        "suspicious_reasons": "|".join(row.suspicious_reasons),
                    }
                )
