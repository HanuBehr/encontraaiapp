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
        "name": "Cold Email",
        "subject_template": "Coleta responsavel de materiais para {business_name}",
        "body_template": (
            "Ola, equipe da {business_name}.\n\n"
            "Atuamos com coleta responsavel e logistica reversa para materiais de alto impacto, "
            "com foco em operacoes locais como {category_text} em {city_text}.\n\n"
            "{material_text}\n\n"
            "Se fizer sentido, posso enviar uma explicacao curta de como funciona a retirada e a destinacao correta.\n\n"
            "Atenciosamente,\n"
            "Equipe de Logistica Reversa"
        ),
    },
    TemplateKey.COLD_WHATSAPP: {
        "channel": OutreachChannel.WHATSAPP,
        "name": "Cold WhatsApp",
        "subject_template": None,
        "body_template": (
            "Ola, tudo bem? Aqui e da equipe de logistica reversa.\n\n"
            "Trabalhamos com coleta responsavel de materiais de alto impacto para negocios como {business_name} "
            "em {city_text}, incluindo {material_short_text}.\n\n"
            "Se for util, posso explicar rapidinho como funciona a retirada e a destinacao correta."
        ),
    },
    TemplateKey.FOLLOW_UP_EMAIL: {
        "channel": OutreachChannel.EMAIL,
        "name": "Follow-up Email",
        "subject_template": "Retomando contato com {business_name}",
        "body_template": (
            "Ola, equipe da {business_name}.\n\n"
            "Retomando meu contato anterior sobre coleta responsavel e logistica reversa para materiais "
            "gerados em {category_text}.\n\n"
            "Se houver interesse, posso enviar um resumo objetivo com o fluxo de atendimento em {city_text}.\n\n"
            "Fico a disposicao."
        ),
    },
    TemplateKey.FOLLOW_UP_WHATSAPP: {
        "channel": OutreachChannel.WHATSAPP,
        "name": "Follow-up WhatsApp",
        "subject_template": None,
        "body_template": (
            "Ola, estou retomando o contato sobre a coleta responsavel de materiais gerados por {business_name}.\n\n"
            "Se ainda fizer sentido, posso mandar um resumo curto de como atendemos {city_text}."
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
                message=f"Outreach draft generated using template {template.key.value}.",
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
        material_labels = {
            "catalytic_converters": "catalisadores",
            "batteries": "baterias",
            "electronics": "eletronicos e placas",
            "repair_waste": "residuos tecnicos de manutencao",
        }
        relevant_materials = [
            material_labels[key]
            for key, details in (lead.material_profile or {}).items()
            if details.get("relevant") and key in material_labels
        ]
        material_short_text = ", ".join(relevant_materials) if relevant_materials else "materiais automotivos e eletronicos"
        material_text = (
            f"Percebemos potencial aderencia a materiais como {material_short_text}."
            if relevant_materials
            else "Atendemos materiais automotivos e eletronicos com destinacao correta."
        )
        return {
            "business_name": lead.business_name,
            "city_text": lead.city or "sua regiao",
            "neighborhood_text": lead.neighborhood or "seu bairro",
            "category_text": lead.category or "operacoes locais",
            "material_short_text": material_short_text,
            "material_text": material_text,
        }
