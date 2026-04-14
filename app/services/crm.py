from __future__ import annotations

from sqlalchemy.orm import Session

from app.enums import ActivityAction, LeadStatus
from app.models.activity_log import ActivityLog
from app.repositories.lead_repository import LeadRepository
from app.schemas.lead import LeadUpdateRequest
from app.services.normalization import normalize_tags


class CRMService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = LeadRepository(db)

    def update_lead(self, lead_id: int, payload: LeadUpdateRequest, *, actor: str = "system"):
        lead = self.repository.get_by_id(lead_id)
        if lead is None:
            raise ValueError(f"Lead {lead_id} not found.")
        organization_id = lead.organization_id or self.repository.organization_id

        changed_fields: list[str] = []

        if "status" in payload.model_fields_set and payload.status is not None and lead.status != payload.status:
            previous_status = lead.status
            lead.status = payload.status
            changed_fields.append("status")
            self.db.add(
                ActivityLog(
                    organization_id=organization_id,
                    lead_id=lead.id,
                    entity_type="lead",
                    entity_id=lead.id,
                    action=ActivityAction.STATUS_CHANGED,
                    actor=actor,
                    message=f"Lead status changed from {previous_status.value} to {lead.status.value}.",
                    metadata_json={"from": previous_status.value, "to": lead.status.value},
                )
            )

        if "notes" in payload.model_fields_set and payload.notes != lead.notes:
            previous_notes = lead.notes
            lead.notes = payload.notes
            changed_fields.append("notes")
            if payload.notes:
                self.db.add(
                    ActivityLog(
                        organization_id=organization_id,
                        lead_id=lead.id,
                        entity_type="lead",
                        entity_id=lead.id,
                        action=ActivityAction.NOTE_ADDED,
                        actor=actor,
                        message="Lead notes updated.",
                        metadata_json={"previous_notes": previous_notes, "notes": payload.notes},
                    )
                )

        if "tags" in payload.model_fields_set and payload.tags is not None:
            normalized_tags = normalize_tags(payload.tags)
            if normalized_tags != (lead.tags or []):
                lead.tags = normalized_tags
                changed_fields.append("tags")

        if "follow_up_date" in payload.model_fields_set and payload.follow_up_date != lead.follow_up_date:
            lead.follow_up_date = payload.follow_up_date
            changed_fields.append("follow_up_date")

        if "do_not_contact" in payload.model_fields_set and payload.do_not_contact is not None:
            if lead.do_not_contact != payload.do_not_contact:
                lead.do_not_contact = payload.do_not_contact
                changed_fields.append("do_not_contact")

            if payload.do_not_contact and lead.status != LeadStatus.DO_NOT_CONTACT:
                previous_status = lead.status
                lead.status = LeadStatus.DO_NOT_CONTACT
                if "status" not in changed_fields:
                    changed_fields.append("status")
                self.db.add(
                    ActivityLog(
                        organization_id=organization_id,
                        lead_id=lead.id,
                        entity_type="lead",
                        entity_id=lead.id,
                        action=ActivityAction.STATUS_CHANGED,
                        actor=actor,
                        message=f"Lead status changed from {previous_status.value} to {lead.status.value}.",
                        metadata_json={"from": previous_status.value, "to": lead.status.value},
                    )
                )

        if (
            "status" in payload.model_fields_set
            and payload.status == LeadStatus.DO_NOT_CONTACT
            and not lead.do_not_contact
        ):
            lead.do_not_contact = True
            if "do_not_contact" not in changed_fields:
                changed_fields.append("do_not_contact")

        if changed_fields:
            self.db.add(
                ActivityLog(
                    organization_id=organization_id,
                    lead_id=lead.id,
                    entity_type="lead",
                    entity_id=lead.id,
                    action=ActivityAction.LEAD_UPDATED,
                    actor=actor,
                    message="Lead fields updated.",
                    metadata_json={"changed_fields": changed_fields},
                )
            )

        self.db.commit()
        return self.repository.get_detail(lead.id)
