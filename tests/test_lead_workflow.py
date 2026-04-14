from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace

from app.enums import LeadSourceType, LeadStatus, TemplateKey
from app.services.lead_workflow import (
    ACTION_QUEUE_SCORE_MIN,
    SORT_BUSINESS_NAME,
    SORT_FOLLOW_UP_DATE,
    SORT_HIGHEST_PRIORITY,
    SORT_RECENTLY_UPDATED,
    WORKFLOW_VIEWS,
    apply_operator_quick_filters,
    apply_workflow_view,
    build_filtered_queue,
    build_queue_stats,
    contact_state,
    default_template_key_for_lead,
    has_any_contact,
    has_direct_channel,
    is_follow_up_due,
    is_uncontacted,
    matches_search,
    next_best_action,
    sort_leads,
)


def _lead(**overrides):
    defaults = {
        "id": 1,
        "business_name": "Oficina Base",
        "category": "oficina mecanica",
        "neighborhood": None,
        "city": "Sao Paulo",
        "state": "SP",
        "email": None,
        "phone": None,
        "whatsapp": None,
        "website": None,
        "lead_source_type": LeadSourceType.GOOGLE_PLACES,
        "lead_score": 0,
        "status": LeadStatus.NEW,
        "do_not_contact": False,
        "is_duplicate": False,
        "follow_up_date": None,
        "last_contacted_at": None,
        "last_enriched_at": None,
        "updated_at": datetime(2026, 4, 13, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_workflow_constants_preserve_current_defaults() -> None:
    assert ACTION_QUEUE_SCORE_MIN == 70
    assert WORKFLOW_VIEWS == [
        "Action queue",
        "Ready for outreach",
        "Needs enrichment",
        "Follow-up due",
        "All leads",
    ]


def test_contact_state_separates_direct_channel_from_any_contact() -> None:
    phone_only = _lead(phone="+5511999999999")

    state = contact_state(phone_only)

    assert state.has_phone is True
    assert state.has_any_contact is True
    assert state.has_direct_channel is False
    assert state.contact_count == 1
    assert state.direct_channel_count == 0
    assert has_any_contact(phone_only) is True
    assert has_direct_channel(phone_only) is False


def test_contact_state_treats_email_and_whatsapp_as_direct_channels() -> None:
    lead = _lead(email="ops@example.com", whatsapp="+5511888888888")

    state = contact_state(lead)

    assert state.has_email is True
    assert state.has_whatsapp is True
    assert state.has_direct_channel is True
    assert state.direct_channel_count == 2


def test_follow_up_due_and_uncontacted_match_current_policy() -> None:
    due_lead = _lead(status=LeadStatus.CONTACTED, follow_up_date=date(2026, 4, 12))
    future_lead = _lead(status=LeadStatus.CONTACTED, follow_up_date=date(2026, 4, 14))
    contacted_lead = _lead(status=LeadStatus.NEW, last_contacted_at=datetime.now(timezone.utc))

    assert is_follow_up_due(due_lead, today=date(2026, 4, 13)) is True
    assert is_follow_up_due(future_lead, today=date(2026, 4, 13)) is False
    assert is_uncontacted(_lead(status=LeadStatus.REVIEWED)) is True
    assert is_uncontacted(contacted_lead) is False
    assert is_uncontacted(_lead(status=LeadStatus.CONTACTED)) is False


def test_next_best_action_preserves_existing_priority_order() -> None:
    assert (
        next_best_action(_lead(do_not_contact=True))
        == "Do not contact is active. Keep outreach blocked and preserve the reason in notes."
    )
    assert (
        next_best_action(_lead(status=LeadStatus.NEW, email="ops@example.com"))
        == "Review fit, confirm the public evidence, and update the pipeline status."
    )
    assert (
        next_best_action(_lead(status=LeadStatus.REVIEWED, email="ops@example.com"))
        == "Find more public contact info before outreach."
    )
    assert (
        next_best_action(
            _lead(
                status=LeadStatus.CONTACTED,
                email="ops@example.com",
                follow_up_date=date(2026, 4, 12),
                last_enriched_at=datetime.now(timezone.utc),
            ),
            today=date(2026, 4, 13),
        )
        == "A follow-up is due. Review the latest notes and prepare the next outreach draft."
    )


def test_default_template_key_for_lead_matches_current_selection_policy() -> None:
    template_keys = [
        TemplateKey.COLD_EMAIL.value,
        TemplateKey.COLD_WHATSAPP.value,
        TemplateKey.FOLLOW_UP_EMAIL.value,
        TemplateKey.FOLLOW_UP_WHATSAPP.value,
    ]

    assert default_template_key_for_lead(_lead(status=LeadStatus.NEW, email="ops@example.com"), template_keys) == "cold_email"
    assert (
        default_template_key_for_lead(_lead(status=LeadStatus.NEW, whatsapp="+5511888888888"), template_keys)
        == "cold_whatsapp"
    )
    assert (
        default_template_key_for_lead(_lead(status=LeadStatus.CONTACTED, email="ops@example.com"), template_keys)
        == "follow_up_email"
    )
    assert (
        default_template_key_for_lead(_lead(status=LeadStatus.REPLIED, whatsapp="+5511888888888"), template_keys)
        == "follow_up_whatsapp"
    )
    assert default_template_key_for_lead(_lead(status=LeadStatus.REVIEWED), template_keys) == "cold_email"


def test_apply_workflow_view_preserves_lane_definitions() -> None:
    enriched_at = datetime(2026, 4, 10, tzinfo=timezone.utc)
    action_lead = _lead(id=1, phone="+5511999999999", lead_score=70, status=LeadStatus.REVIEWED)
    low_score = _lead(id=2, phone="+5511888888888", lead_score=69, status=LeadStatus.REVIEWED)
    ready = _lead(id=3, email="ops@example.com", lead_score=75, status=LeadStatus.CONTACTED)
    needs_enrichment = _lead(id=4, lead_score=20, status=LeadStatus.APPROVED)
    follow_up = _lead(
        id=5,
        email="follow@example.com",
        lead_score=10,
        status=LeadStatus.REPLIED,
        follow_up_date=date(2000, 1, 1),
        last_enriched_at=enriched_at,
    )
    dnc = _lead(id=6, email="blocked@example.com", lead_score=99, do_not_contact=True)
    leads = [action_lead, low_score, ready, needs_enrichment, follow_up, dnc]

    assert [lead.id for lead in apply_workflow_view(leads, "Action queue")] == [1]
    assert [lead.id for lead in apply_workflow_view(leads, "Ready for outreach")] == [3]
    assert [lead.id for lead in apply_workflow_view(leads, "Needs enrichment")] == [1, 2, 3, 4]
    assert [lead.id for lead in apply_workflow_view(leads, "Follow-up due")] == [5]
    assert apply_workflow_view(leads, "All leads") == leads


def test_apply_operator_quick_filters_preserves_checkbox_semantics() -> None:
    leads = [
        _lead(id=1, email="a@example.com", lead_score=80, status=LeadStatus.NEW),
        _lead(id=2, email="b@example.com", lead_score=80, status=LeadStatus.CONTACTED),
        _lead(id=3, phone="+5511999999999", lead_score=60, status=LeadStatus.REVIEWED),
        _lead(id=4, lead_score=90, status=LeadStatus.APPROVED),
        _lead(id=5, email="dup@example.com", lead_score=90, status=LeadStatus.REVIEWED, is_duplicate=True),
    ]

    filtered = apply_operator_quick_filters(
        leads,
        hide_duplicates=True,
        require_contact=True,
        high_score_only=True,
        only_uncontacted=True,
    )

    assert [lead.id for lead in filtered] == [1]


def test_matches_search_uses_current_streamlit_haystack_fields() -> None:
    lead = _lead(
        business_name="Auto Eletrica Vale",
        category="auto eletrica",
        neighborhood="Centro",
        city="Campinas",
        state="SP",
        website="https://autovale.example.com",
        email="contato@autovale.example.com",
        phone="+5519999999999",
        whatsapp="+5519888888888",
        status=LeadStatus.REVIEWED,
        lead_source_type=LeadSourceType.GOOGLE_PLACES,
    )

    assert matches_search(lead, "campinas") is True
    assert matches_search(lead, "reviewed") is True
    assert matches_search(lead, "google_places") is True
    assert matches_search(lead, "missing") is False
    assert matches_search(lead, "") is True


def test_sort_leads_uses_backend_sort_keys_with_existing_ordering() -> None:
    t1 = datetime(2026, 4, 10, 10, tzinfo=timezone.utc)
    t2 = datetime(2026, 4, 11, 10, tzinfo=timezone.utc)
    leads = [
        _lead(id=1, business_name="Beta", lead_score=80, updated_at=t1, follow_up_date=None),
        _lead(id=2, business_name="alpha", lead_score=95, updated_at=t1, follow_up_date=date(2026, 4, 20)),
        _lead(id=3, business_name="Delta", lead_score=95, updated_at=t2, follow_up_date=date(2026, 4, 18)),
        _lead(id=4, business_name="Alpha", lead_score=70, updated_at=t2, follow_up_date=date(2026, 4, 18)),
    ]

    assert [lead.id for lead in sort_leads(leads, SORT_RECENTLY_UPDATED)] == [4, 3, 2, 1]
    assert [lead.id for lead in sort_leads(leads, SORT_HIGHEST_PRIORITY)] == [3, 2, 1, 4]
    assert [lead.id for lead in sort_leads(leads, SORT_FOLLOW_UP_DATE)] == [3, 4, 2, 1]
    assert [lead.id for lead in sort_leads(leads, SORT_BUSINESS_NAME)] == [2, 4, 1, 3]


def test_build_filtered_queue_combines_lane_quick_search_and_sort_policy() -> None:
    leads = [
        _lead(id=1, business_name="Oficina A", city="Santos", email="a@example.com", lead_score=80),
        _lead(id=2, business_name="Oficina B", city="Campinas", email="b@example.com", lead_score=90),
        _lead(id=3, business_name="Oficina C", city="Campinas", email="c@example.com", lead_score=60),
        _lead(id=4, business_name="Oficina D", city="Campinas", lead_score=95),
    ]

    filtered = build_filtered_queue(
        leads,
        workflow_view="Action queue",
        search_term="campinas",
        sort_key=SORT_HIGHEST_PRIORITY,
        hide_duplicates=True,
        require_contact=True,
        high_score_only=True,
        only_uncontacted=True,
    )

    assert [lead.id for lead in filtered] == [2]


def test_build_queue_stats_returns_non_rendering_queue_summary() -> None:
    stats = build_queue_stats(
        [
            _lead(id=1, email="a@example.com", last_enriched_at=None),
            _lead(id=2, phone="+5511999999999", last_enriched_at=datetime.now(timezone.utc)),
            _lead(id=3, follow_up_date=date(2000, 1, 1), status=LeadStatus.CONTACTED),
            _lead(id=4, do_not_contact=True, last_enriched_at=None),
        ]
    )

    assert stats.as_dict() == {
        "queue_size": 4,
        "any_contact": 2,
        "needs_enrichment": 2,
        "follow_up_due": 1,
    }
