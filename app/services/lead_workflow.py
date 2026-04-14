from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol, TypeVar

from app.enums import LeadStatus, TemplateKey


WORKFLOW_VIEWS = [
    "Action queue",
    "Ready for outreach",
    "Needs enrichment",
    "Follow-up due",
    "All leads",
]
WORKFLOW_VIEW_DESCRIPTIONS = {
    "Action queue": "Best leads to review before first outreach: contactable, high-priority, and not yet contacted.",
    "Ready for outreach": "High-priority leads with email or WhatsApp already stored and no do-not-contact block.",
    "Needs enrichment": "Saved leads that still need a public contact refresh or stronger evidence before outreach.",
    "Follow-up due": "Saved leads with a due or overdue follow-up date.",
    "All leads": "Every saved lead that matches the current filters.",
}
ACTIVE_STATUSES = {
    LeadStatus.NEW,
    LeadStatus.REVIEWED,
    LeadStatus.APPROVED,
    LeadStatus.CONTACTED,
    LeadStatus.REPLIED,
    LeadStatus.INTERESTED,
}
FOLLOW_UP_STATUSES = {
    LeadStatus.CONTACTED,
    LeadStatus.REPLIED,
    LeadStatus.INTERESTED,
}
ACTION_QUEUE_SCORE_MIN = 70
ACTIVE_STATUS_VALUES = {status.value for status in ACTIVE_STATUSES}
FOLLOW_UP_STATUS_VALUES = {status.value for status in FOLLOW_UP_STATUSES}
UNCONTACTED_STATUS_VALUES = {
    LeadStatus.NEW.value,
    LeadStatus.REVIEWED.value,
    LeadStatus.APPROVED.value,
}
SORT_RECENTLY_UPDATED = "recently_updated"
SORT_HIGHEST_PRIORITY = "highest_priority"
SORT_FOLLOW_UP_DATE = "follow_up_date"
SORT_BUSINESS_NAME = "business_name"
SUPPORTED_SORT_KEYS = (
    SORT_RECENTLY_UPDATED,
    SORT_HIGHEST_PRIORITY,
    SORT_FOLLOW_UP_DATE,
    SORT_BUSINESS_NAME,
)


class WorkflowLead(Protocol):
    id: int
    business_name: str
    category: str | None
    neighborhood: str | None
    city: str | None
    state: str | None
    email: str | None
    phone: str | None
    whatsapp: str | None
    website: str | None
    lead_source_type: object | None
    lead_score: int
    status: LeadStatus | str
    do_not_contact: bool
    is_duplicate: bool
    follow_up_date: date | None
    last_contacted_at: datetime | None
    last_enriched_at: datetime | None
    updated_at: datetime


WorkflowLeadT = TypeVar("WorkflowLeadT", bound=WorkflowLead)


@dataclass(frozen=True, slots=True)
class ContactState:
    has_email: bool
    has_phone: bool
    has_whatsapp: bool
    has_direct_channel: bool
    has_any_contact: bool
    contact_count: int
    direct_channel_count: int


@dataclass(frozen=True, slots=True)
class QueueStats:
    queue_size: int
    any_contact: int
    needs_enrichment: int
    follow_up_due: int

    def as_dict(self) -> dict[str, int]:
        return {
            "queue_size": self.queue_size,
            "any_contact": self.any_contact,
            "needs_enrichment": self.needs_enrichment,
            "follow_up_due": self.follow_up_due,
        }


def status_value(value: LeadStatus | str | object | None) -> str | None:
    if value is None:
        return None
    enum_value = getattr(value, "value", None)
    return str(enum_value if enum_value is not None else value)


def status_in(value: LeadStatus | str | object | None, allowed_values: set[str]) -> bool:
    normalized = status_value(value)
    return normalized in allowed_values if normalized is not None else False


def contact_state(lead: WorkflowLead) -> ContactState:
    has_email = bool(lead.email)
    has_phone = bool(lead.phone)
    has_whatsapp = bool(lead.whatsapp)
    return ContactState(
        has_email=has_email,
        has_phone=has_phone,
        has_whatsapp=has_whatsapp,
        has_direct_channel=has_email or has_whatsapp,
        has_any_contact=has_email or has_whatsapp or has_phone,
        contact_count=sum([has_email, has_phone, has_whatsapp]),
        direct_channel_count=sum([has_email, has_whatsapp]),
    )


def has_direct_channel(lead: WorkflowLead) -> bool:
    return contact_state(lead).has_direct_channel


def has_any_contact(lead: WorkflowLead) -> bool:
    return contact_state(lead).has_any_contact


def is_follow_up_due(lead: WorkflowLead, *, today: date | None = None) -> bool:
    # Default matches the previous Streamlit behavior; tests can inject today.
    reference_date = today or date.today()
    return bool(lead.follow_up_date and lead.follow_up_date <= reference_date)


def is_uncontacted(lead: WorkflowLead) -> bool:
    return status_in(lead.status, UNCONTACTED_STATUS_VALUES) and lead.last_contacted_at is None


def next_best_action(lead: WorkflowLead, *, today: date | None = None) -> str:
    lead_status = status_value(lead.status)
    if lead.do_not_contact:
        return "Do not contact is active. Keep outreach blocked and preserve the reason in notes."
    if lead_status == LeadStatus.NEW.value:
        return "Review fit, confirm the public evidence, and update the pipeline status."
    if not lead.last_enriched_at:
        return "Find more public contact info before outreach."
    if is_follow_up_due(lead, today=today):
        return "A follow-up is due. Review the latest notes and prepare the next outreach draft."
    if has_direct_channel(lead):
        return "A direct contact channel is available. Review the details and prepare the draft."
    if has_any_contact(lead):
        return "A phone contact is available. Check whether a public contact refresh can find email or WhatsApp before drafting."
    return "Review the lead and capture the next operator step in notes."


def default_template_key_for_lead(lead: WorkflowLead, template_keys: list[str]) -> str:
    if status_in(lead.status, FOLLOW_UP_STATUS_VALUES):
        if TemplateKey.FOLLOW_UP_EMAIL.value in template_keys and lead.email:
            return TemplateKey.FOLLOW_UP_EMAIL.value
        if TemplateKey.FOLLOW_UP_WHATSAPP.value in template_keys and lead.whatsapp:
            return TemplateKey.FOLLOW_UP_WHATSAPP.value
    else:
        if TemplateKey.COLD_EMAIL.value in template_keys and lead.email:
            return TemplateKey.COLD_EMAIL.value
        if TemplateKey.COLD_WHATSAPP.value in template_keys and lead.whatsapp:
            return TemplateKey.COLD_WHATSAPP.value
    return template_keys[0]


def apply_workflow_view(leads: list[WorkflowLeadT], workflow_view: str) -> list[WorkflowLeadT]:
    if workflow_view == "Action queue":
        return [
            lead
            for lead in leads
            if status_in(lead.status, UNCONTACTED_STATUS_VALUES)
            and not lead.do_not_contact
            and has_any_contact(lead)
            and lead.lead_score >= ACTION_QUEUE_SCORE_MIN
        ]
    if workflow_view == "Ready for outreach":
        return [
            lead
            for lead in leads
            if status_in(lead.status, ACTIVE_STATUS_VALUES)
            and not lead.do_not_contact
            and has_direct_channel(lead)
            and lead.lead_score >= ACTION_QUEUE_SCORE_MIN
        ]
    if workflow_view == "Needs enrichment":
        return [
            lead
            for lead in leads
            if status_in(lead.status, ACTIVE_STATUS_VALUES)
            and not lead.do_not_contact
            and lead.last_enriched_at is None
        ]
    if workflow_view == "Follow-up due":
        return [
            lead
            for lead in leads
            if status_in(lead.status, FOLLOW_UP_STATUS_VALUES)
            and not lead.do_not_contact
            and is_follow_up_due(lead)
        ]
    return leads


def matches_search(lead: WorkflowLead, search_term: str) -> bool:
    if not search_term:
        return True
    search_value = search_term.lower().strip()
    haystack = " ".join(
        [
            lead.business_name,
            lead.category or "",
            lead.neighborhood or "",
            lead.city or "",
            lead.state or "",
            lead.website or "",
            lead.email or "",
            lead.phone or "",
            lead.whatsapp or "",
            status_value(lead.status) or "",
            status_value(lead.lead_source_type) or "",
        ]
    ).lower()
    return search_value in haystack


def sort_leads(leads: list[WorkflowLeadT], sort_key: str = SORT_RECENTLY_UPDATED) -> list[WorkflowLeadT]:
    if sort_key == SORT_HIGHEST_PRIORITY:
        return sorted(
            leads,
            key=lambda lead: (-lead.lead_score, -(lead.updated_at.timestamp()), -lead.id),
        )
    if sort_key == SORT_FOLLOW_UP_DATE:
        return sorted(
            leads,
            key=lambda lead: (
                lead.follow_up_date is None,
                lead.follow_up_date or date.max,
                -lead.lead_score,
                lead.business_name.lower(),
            ),
        )
    if sort_key == SORT_BUSINESS_NAME:
        return sorted(leads, key=lambda lead: (lead.business_name.lower(), lead.id))
    return sorted(leads, key=lambda lead: (lead.updated_at.timestamp(), lead.id), reverse=True)


def apply_operator_quick_filters(
    leads: list[WorkflowLeadT],
    *,
    hide_duplicates: bool,
    require_contact: bool,
    high_score_only: bool,
    only_uncontacted: bool,
) -> list[WorkflowLeadT]:
    filtered: list[WorkflowLeadT] = []
    for lead in leads:
        if hide_duplicates and lead.is_duplicate:
            continue
        if require_contact and not has_any_contact(lead):
            continue
        if high_score_only and lead.lead_score < ACTION_QUEUE_SCORE_MIN:
            continue
        if only_uncontacted and not is_uncontacted(lead):
            continue
        filtered.append(lead)
    return filtered


def build_filtered_queue(
    leads: list[WorkflowLeadT],
    *,
    workflow_view: str,
    search_term: str,
    sort_key: str,
    hide_duplicates: bool,
    require_contact: bool,
    high_score_only: bool,
    only_uncontacted: bool,
) -> list[WorkflowLeadT]:
    filtered = apply_workflow_view(leads, workflow_view)
    filtered = apply_operator_quick_filters(
        filtered,
        hide_duplicates=hide_duplicates,
        require_contact=require_contact,
        high_score_only=high_score_only,
        only_uncontacted=only_uncontacted,
    )
    if search_term.strip():
        filtered = [lead for lead in filtered if matches_search(lead, search_term)]
    return sort_leads(filtered, sort_key)


def build_queue_stats(leads: list[WorkflowLead]) -> QueueStats:
    any_contact = 0
    needs_enrichment = 0
    follow_up_due = 0

    for lead in leads:
        if has_any_contact(lead):
            any_contact += 1
        if lead.last_enriched_at is None and not lead.do_not_contact:
            needs_enrichment += 1
        if is_follow_up_due(lead):
            follow_up_due += 1

    return QueueStats(
        queue_size=len(leads),
        any_contact=any_contact,
        needs_enrichment=needs_enrichment,
        follow_up_due=follow_up_due,
    )
