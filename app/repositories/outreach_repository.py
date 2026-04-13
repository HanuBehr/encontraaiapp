from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import DraftStatus, TemplateKey
from app.models.base import utcnow
from app.models.outreach import OutreachDraft, OutreachTemplate


class OutreachRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_templates(self) -> list[OutreachTemplate]:
        query = select(OutreachTemplate).order_by(OutreachTemplate.channel.asc(), OutreachTemplate.key.asc())
        return self.db.execute(query).scalars().all()

    def get_template_by_key(self, template_key: TemplateKey) -> OutreachTemplate | None:
        query = select(OutreachTemplate).where(OutreachTemplate.key == template_key)
        return self.db.execute(query).scalar_one_or_none()

    def create_template(
        self,
        *,
        key: TemplateKey,
        channel,
        name: str,
        subject_template: str | None,
        body_template: str,
    ) -> OutreachTemplate:
        template = OutreachTemplate(
            key=key,
            channel=channel,
            name=name,
            subject_template=subject_template,
            body_template=body_template,
            is_active=True,
        )
        self.db.add(template)
        self.db.flush()
        return template

    def create_draft(
        self,
        *,
        lead_id: int,
        template_id: int | None,
        channel,
        draft_type: TemplateKey,
        subject: str | None,
        body: str,
        personalization: dict[str, object],
    ) -> OutreachDraft:
        draft = OutreachDraft(
            lead_id=lead_id,
            template_id=template_id,
            channel=channel,
            draft_type=draft_type,
            subject=subject,
            body=body,
            personalization=personalization,
        )
        self.db.add(draft)
        self.db.flush()
        return draft

    def list_drafts_for_lead(self, lead_id: int) -> list[OutreachDraft]:
        query = (
            select(OutreachDraft)
            .where(OutreachDraft.lead_id == lead_id)
            .order_by(OutreachDraft.created_at.desc(), OutreachDraft.id.desc())
        )
        return self.db.execute(query).scalars().all()

    def get_draft(self, draft_id: int) -> OutreachDraft | None:
        return self.db.get(OutreachDraft, draft_id)

    def update_draft_status(
        self,
        draft: OutreachDraft,
        *,
        status: DraftStatus,
        rejected_reason: str | None = None,
    ) -> OutreachDraft:
        draft.status = status
        draft.rejected_reason = rejected_reason
        if status == DraftStatus.APPROVED:
            draft.approved_at = utcnow()
            draft.rejected_reason = None
        elif status == DraftStatus.REJECTED:
            draft.approved_at = None
        else:
            draft.approved_at = None
            draft.rejected_reason = None
        self.db.flush()
        return draft
