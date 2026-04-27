"""Internal draft-only outreach helpers.

This module intentionally supports reviewable message drafts only.
It does not add campaign orchestration or message sending behavior.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.enums import ActivityAction, DraftStatus, OutreachChannel, TemplateKey
from app.models.activity_log import ActivityLog
from app.repositories.lead_repository import LeadRepository
from app.repositories.outreach_repository import OutreachRepository
from app.schemas.outreach import DraftPreviewResponse


DEFAULT_TEMPLATES: dict[TemplateKey, dict[str, Any]] = {
    TemplateKey.COLD_EMAIL: {
        "channel": OutreachChannel.EMAIL,
        "name": "Internal Intro Email Draft",
        "subject_template": "Contato inicial com {business_name}",
        "body_template": (
            "Ola, equipe da {business_name}.\n\n"
            "Este e um rascunho interno de contato inicial gerado a partir de pesquisa publica.\n"
            "Identificamos {business_name} em uma busca por {category_text} em {city_text}.\n\n"
            "{profile_text}\n\n"
            "Se fizer sentido, posso compartilhar um resumo curto do motivo do contato e confirmar a melhor pessoa para continuar a conversa.\n\n"
            "Atenciosamente,\n"
            "Equipe Encontra.ai"
        ),
    },
    TemplateKey.COLD_WHATSAPP: {
        "channel": OutreachChannel.WHATSAPP,
        "name": "Internal Intro WhatsApp Draft",
        "subject_template": None,
        "body_template": (
            "Ola, tudo bem?\n\n"
            "Este e um rascunho interno de contato inicial para {business_name}. "
            "Identificamos o negocio em uma pesquisa publica por {category_text} em {city_text}.\n\n"
            "Se fizer sentido, posso compartilhar um resumo curto do motivo do contato por aqui."
        ),
    },
    TemplateKey.FOLLOW_UP_EMAIL: {
        "channel": OutreachChannel.EMAIL,
        "name": "Internal Follow-up Email Draft",
        "subject_template": "Retomando contato com {business_name}",
        "body_template": (
            "Ola, equipe da {business_name}.\n\n"
            "Este e um rascunho interno de follow-up baseado no contato anterior com o negocio.\n"
            "Estou retomando o contexto relacionado a {category_text} em {city_text}.\n\n"
            "Se houver interesse, posso enviar um resumo objetivo do motivo do contato e alinhar os proximos passos.\n\n"
            "Fico a disposicao."
        ),
    },
    TemplateKey.FOLLOW_UP_WHATSAPP: {
        "channel": OutreachChannel.WHATSAPP,
        "name": "Internal Follow-up WhatsApp Draft",
        "subject_template": None,
        "body_template": (
            "Ola, estou retomando o contato com {business_name}.\n\n"
            "Este e um rascunho interno de follow-up referente ao negocio identificado em {city_text}.\n"
            "Se ainda fizer sentido, posso mandar um resumo curto do contexto por aqui."
        ),
    },
}


class SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return ""


class OutreachService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.lead_repository = LeadRepository(db)
        self.outreach_repository = OutreachRepository(db)

    def ensure_default_templates(self) -> list:
        templates = self.outreach_repository.list_templates()
        existing_keys = {template.key for template in templates}

        for template_key, payload in DEFAULT_TEMPLATES.items():
            if template_key in existing_keys:
                continue
            self.outreach_repository.create_template(
                key=template_key,
                channel=payload["channel"],
                name=payload["name"],
                subject_template=payload["subject_template"],
                body_template=payload["body_template"],
            )

        if len(existing_keys) != len(DEFAULT_TEMPLATES):
            self.db.commit()
        return self.outreach_repository.list_templates()

    def list_templates(self):
        return self.ensure_default_templates()

    def preview_draft(self, lead_id: int, template_key: TemplateKey) -> DraftPreviewResponse:
        template = self._get_template(template_key)
        lead = self.lead_repository.get_detail(lead_id)
        if lead is None:
            raise ValueError(f"Lead {lead_id} not found.")

        context = self._build_context(lead)
        subject = template.subject_template.format_map(SafeFormatDict(context)) if template.subject_template else None
        body = template.body_template.format_map(SafeFormatDict(context))
        return DraftPreviewResponse(
            lead_id=lead.id,
            template_key=template.key,
            channel=template.channel,
            subject=subject,
            body=body,
            personalization=context,
        )

    def generate_draft(self, lead_id: int, template_key: TemplateKey, *, actor: str = "system"):
        lead = self.lead_repository.get_by_id(lead_id)
        if lead is None:
            raise ValueError(f"Lead {lead_id} not found.")
        preview = self.preview_draft(lead_id, template_key)
        template = self._get_template(template_key)
        draft = self.outreach_repository.create_draft(
            lead_id=lead_id,
            template_id=template.id,
            channel=template.channel,
            draft_type=template.key,
            subject=preview.subject,
            body=preview.body,
            personalization=preview.personalization,
        )
        self.db.add(
            ActivityLog(
                organization_id=lead.organization_id or self.lead_repository.organization_id,
                lead_id=lead_id,
                entity_type="lead",
                entity_id=lead_id,
                action=ActivityAction.DRAFT_GENERATED,
                actor=actor,
                message=f"Internal outreach draft generated using template {template.key.value}.",
                metadata_json={"template_key": template.key.value, "draft_id": draft.id},
            )
        )
        self.db.commit()
        return draft

    def list_drafts_for_lead(self, lead_id: int):
        self.ensure_default_templates()
        return self.outreach_repository.list_drafts_for_lead(lead_id)

    def update_draft_status(
        self,
        draft_id: int,
        *,
        status: DraftStatus,
        rejected_reason: str | None = None,
    ):
        draft = self.outreach_repository.get_draft(draft_id)
        if draft is None:
            raise ValueError(f"Draft {draft_id} not found.")
        updated = self.outreach_repository.update_draft_status(
            draft,
            status=status,
            rejected_reason=rejected_reason,
        )
        self.db.commit()
        return updated

    def _get_template(self, template_key: TemplateKey):
        self.ensure_default_templates()
        template = self.outreach_repository.get_template_by_key(template_key)
        if template is None:
            raise ValueError(f"Template {template_key.value} not found.")
        return template

    @staticmethod
    def _build_context(lead) -> dict[str, str]:
        profile_signal_labels = {
            "appointments": "agendamento publico",
            "catalog": "catalogo de produtos ou servicos",
            "delivery": "entrega ou retirada",
            "support": "atendimento publico",
        }
        relevant_profile_signals = [
            profile_signal_labels[key]
            for key, details in (lead.material_profile or {}).items()
            if details.get("relevant") and key in profile_signal_labels
        ]
        profile_short_text = (
            ", ".join(relevant_profile_signals)
            if relevant_profile_signals
            else "presenca publica basica do negocio"
        )
        profile_text = (
            f"Tambem identificamos sinais publicos como {profile_short_text}."
            if relevant_profile_signals
            else "A busca encontrou apenas sinais publicos basicos do negocio."
        )
        return {
            "business_name": lead.business_name,
            "city_text": lead.city or "sua regiao",
            "neighborhood_text": lead.neighborhood or "seu bairro",
            "category_text": lead.category or "operacoes locais",
            "profile_short_text": profile_short_text,
            "profile_text": profile_text,
        }
