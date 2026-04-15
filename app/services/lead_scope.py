from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.models.import_batch import ImportBatch
from app.repositories.lead_repository import LeadRepository
from app.schemas.lead import LeadListFilters, LeadScopeRequest


@dataclass(slots=True)
class ResolvedLeadScope:
    scope_type: str
    scope_label: str
    lead_ids: list[int]
    filters: LeadListFilters
    requested_lead_ids: list[int] = field(default_factory=list)
    missing_lead_ids: list[int] = field(default_factory=list)
    import_batch: ImportBatch | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def requested_count(self) -> int:
        if self.requested_lead_ids:
            return len(self.requested_lead_ids)
        return len(self.lead_ids)


class LeadScopeResolver:
    def __init__(self, db: Session) -> None:
        self.repository = LeadRepository(db)

    def resolve(self, payload: LeadScopeRequest) -> ResolvedLeadScope:
        if payload.lead_ids is not None:
            return self._resolve_explicit_lead_ids(payload.lead_ids)
        if payload.filters is not None:
            return self._resolve_filters(payload.filters)
        return self._resolve_latest_import_batch()

    def _resolve_explicit_lead_ids(self, lead_ids: list[int]) -> ResolvedLeadScope:
        requested_ids = self._unique_ids(lead_ids)
        leads = self.repository.list_export_leads_by_ids(requested_ids)
        resolved_ids = [lead.id for lead in leads]
        resolved_id_set = set(resolved_ids)
        missing_ids = [lead_id for lead_id in requested_ids if lead_id not in resolved_id_set]
        metadata = {
            "scope_type": "lead_ids",
            "scope_label": "Selected leads",
            "requested_count": len(requested_ids),
            "missing_lead_ids": missing_ids,
        }
        return ResolvedLeadScope(
            scope_type="lead_ids",
            scope_label="Selected leads",
            lead_ids=resolved_ids,
            filters=LeadListFilters(),
            requested_lead_ids=requested_ids,
            missing_lead_ids=missing_ids,
            metadata=metadata,
        )

    def _resolve_filters(self, filters: LeadListFilters) -> ResolvedLeadScope:
        lead_ids = self.repository.list_lead_ids(filters)
        metadata = {
            "scope_type": "filters",
            "scope_label": "Current filtered lead set",
            "lead_count": len(lead_ids),
        }
        return ResolvedLeadScope(
            scope_type="filters",
            scope_label="Current filtered lead set",
            lead_ids=lead_ids,
            filters=filters,
            metadata=metadata,
        )

    def _resolve_latest_import_batch(self) -> ResolvedLeadScope:
        batch = self.repository.get_latest_completed_import_batch()
        if batch is None:
            raise ValueError("No completed import batch with leads was found.")

        lead_ids = self.repository.list_lead_ids_for_import_batch(batch.id)
        metadata = {
            "scope_type": "latest_import_batch",
            "scope_label": f"Latest import batch #{batch.id}",
            "import_batch_id": batch.id,
            "lead_count": len(lead_ids),
        }
        return ResolvedLeadScope(
            scope_type="latest_import_batch",
            scope_label=f"Latest import batch #{batch.id}",
            lead_ids=lead_ids,
            filters=LeadListFilters(),
            import_batch=batch,
            metadata=metadata,
        )

    @staticmethod
    def _unique_ids(lead_ids: list[int]) -> list[int]:
        return list(dict.fromkeys(int(lead_id) for lead_id in lead_ids))
