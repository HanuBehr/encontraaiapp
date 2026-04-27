from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.enums import LeadSourceType, LeadStatus
from app.models.lead import Lead
from app.models.organization import Organization
from app.repositories.lead_repository import LeadRepository
from app.repositories.organization_repository import get_or_create_default_organization
from app.schemas.discovery import DiscoveryLeadCandidate
from app.services.normalization import normalize_business_name


def _organization(slug: str) -> Organization:
    return Organization(slug=slug, name=slug.title(), display_name=slug.title())


def _lead(
    business_name: str,
    *,
    organization: Organization | None,
    google_place_id: str | None = None,
    city: str = "Campinas",
    phone: str | None = None,
) -> Lead:
    return Lead(
        organization=organization,
        business_name=business_name,
        normalized_business_name=normalize_business_name(business_name) or business_name.lower(),
        category="materiais de construcao",
        city=city,
        state="SP",
        phone=phone,
        whatsapp=phone,
        google_place_id=google_place_id,
        lead_source_type=LeadSourceType.GOOGLE_PLACES,
        status=LeadStatus.NEW,
    )


def _candidate(name: str, *, google_place_id: str, domain: str = "shared.example") -> DiscoveryLeadCandidate:
    return DiscoveryLeadCandidate(
        business_name=name,
        normalized_business_name=normalize_business_name(name) or name.lower(),
        category="materiais de construcao",
        city="Campinas",
        state="SP",
        domain=domain,
        google_place_id=google_place_id,
        source_provider="google_places",
        source_url=f"https://maps.example/{google_place_id}",
        lead_source_type=LeadSourceType.GOOGLE_PLACES,
    )


def test_google_place_id_is_unique_per_organization(db_session) -> None:
    org_a = _organization("tenant-a")
    org_b = _organization("client-b")
    db_session.add_all([org_a, org_b])
    db_session.flush()

    db_session.add_all(
        [
            _lead("Casa Alpha", organization=org_a, google_place_id="place-shared"),
            _lead("Casa Alpha", organization=org_b, google_place_id="place-shared"),
        ]
    )
    db_session.commit()

    assert db_session.scalar(select(func.count(Lead.id)).where(Lead.google_place_id == "place-shared")) == 2

    db_session.add(_lead("Casa Alpha Filial", organization=org_a, google_place_id="place-shared"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_default_repository_scope_preserves_legacy_null_leads_without_cross_org_leaks(db_session) -> None:
    default_org = get_or_create_default_organization(db_session)
    other_org = _organization("other-client")
    db_session.add(other_org)
    db_session.flush()

    legacy_lead = _lead("Legacy Lead", organization=None, google_place_id="legacy-place")
    default_lead = _lead("Default Lead", organization=default_org, google_place_id="default-place")
    other_lead = _lead("Other Lead", organization=other_org, google_place_id="other-place")
    db_session.add_all([legacy_lead, default_lead, other_lead])
    db_session.commit()

    default_repo = LeadRepository(db_session)
    default_ids = {lead.id for lead in default_repo.list_all_leads()}

    assert {legacy_lead.id, default_lead.id}.issubset(default_ids)
    assert other_lead.id not in default_ids
    assert default_repo.get_by_id(other_lead.id) is None
    assert default_repo.get_detail(other_lead.id) is None
    assert default_repo.get_with_related(other_lead.id) is None

    other_repo = LeadRepository(db_session, organization_id=other_org.id)

    assert other_repo.get_by_id(other_lead.id) == other_lead
    assert other_repo.get_by_id(legacy_lead.id) is None
    assert other_repo.get_by_id(default_lead.id) is None


def test_discovery_upsert_matches_leads_only_inside_repository_organization(db_session) -> None:
    org_a = _organization("tenant-a")
    org_b = _organization("tenant-b")
    db_session.add_all([org_a, org_b])
    db_session.flush()

    candidate = _candidate("Casa Alpha", google_place_id="place-shared")
    repo_a = LeadRepository(db_session, organization_id=org_a.id)
    repo_b = LeadRepository(db_session, organization_id=org_b.id)

    lead_a, created_a = repo_a.upsert_from_discovery(candidate)
    lead_a_again, created_a_again = repo_a.upsert_from_discovery(candidate)
    lead_b, created_b = repo_b.upsert_from_discovery(candidate)
    db_session.commit()

    assert created_a is True
    assert created_a_again is False
    assert lead_a_again.id == lead_a.id
    assert created_b is True
    assert lead_b.id != lead_a.id
    assert lead_a.organization_id == org_a.id
    assert lead_b.organization_id == org_b.id


def test_duplicate_candidate_id_lookup_does_not_cross_organization_boundaries(db_session) -> None:
    org_a = _organization("dedupe-a")
    org_b = _organization("dedupe-b")
    db_session.add_all([org_a, org_b])
    db_session.flush()

    lead_a = _lead("Casa Duplicada", organization=org_a, phone="+5511999999999")
    lead_b = _lead("Casa Duplicada", organization=org_b, phone="+5511999999999")
    db_session.add_all([lead_a, lead_b])
    db_session.commit()

    repo_a = LeadRepository(db_session, organization_id=org_a.id)
    repo_b = LeadRepository(db_session, organization_id=org_b.id)

    assert repo_a.get_by_ids([lead_a.id, lead_b.id]) == [lead_a]
    assert repo_b.get_by_ids([lead_a.id, lead_b.id]) == [lead_b]
