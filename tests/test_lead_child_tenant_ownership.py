from __future__ import annotations

import pytest
from sqlalchemy import inspect, select

from app.config import Settings
from app.enums import ActivityAction, ContactType, LeadSourceType, LeadStatus
from app.models.activity_log import ActivityLog
from app.models.lead import Lead
from app.models.lead_contact import LeadContact
from app.models.lead_enrichment_record import LeadEnrichmentRecord
from app.models.organization import Organization
from app.repositories.lead_repository import LeadRepository
from app.repositories.organization_repository import get_or_create_default_organization
from app.schemas.lead import LeadUpdateRequest
from app.services.crm import CRMService
from app.services.enrichment import EnrichmentService
from app.services.normalization import normalize_business_name


def _organization(slug: str) -> Organization:
    return Organization(slug=slug, name=slug.title(), display_name=slug.title())


def _lead(business_name: str, *, organization: Organization | None) -> Lead:
    return Lead(
        organization=organization,
        business_name=business_name,
        normalized_business_name=normalize_business_name(business_name) or business_name.lower(),
        category="materiais de construcao",
        city="Campinas",
        state="SP",
        lead_source_type=LeadSourceType.GOOGLE_PLACES,
        status=LeadStatus.NEW,
    )


def _settings() -> Settings:
    return Settings(APP_ENV="test", DATABASE_URL="sqlite://", EXPORT_DIR="./data/exports", GOOGLE_API_KEY="")


def test_lead_child_tenant_columns_and_indexes_are_created(session_factory) -> None:
    engine = session_factory.kw["bind"]
    inspector = inspect(engine)

    for table_name in ("lead_contacts", "lead_enrichment_records", "activity_logs"):
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        assert "organization_id" in columns

    indexes = {
        table_name: {index["name"] for index in inspector.get_indexes(table_name)}
        for table_name in ("lead_contacts", "lead_enrichment_records", "activity_logs")
    }

    assert "ix_lead_contacts_org_type_value" in indexes["lead_contacts"]
    assert "ix_lead_contacts_org_lead_primary" in indexes["lead_contacts"]
    assert "ix_lead_enrichment_org_lead_fetched" in indexes["lead_enrichment_records"]
    assert "ix_activity_logs_org_lead_created" in indexes["activity_logs"]
    assert "ix_activity_logs_org_action_created" in indexes["activity_logs"]


def test_add_contact_sets_organization_and_rejects_out_of_scope_lead(db_session) -> None:
    org_a = _organization("tenant-a")
    org_b = _organization("tenant-b")
    lead_a = _lead("Casa Alpha", organization=org_a)
    lead_b = _lead("Casa Beta", organization=org_b)
    db_session.add_all([org_a, org_b, lead_a, lead_b])
    db_session.commit()

    repo_a = LeadRepository(db_session, organization_id=org_a.id)

    contact = repo_a.add_contact_if_missing(
        lead_id=lead_a.id,
        contact_type=ContactType.EMAIL,
        raw_value="alpha@example.com",
        normalized_value="alpha@example.com",
        source_url="https://alpha.example",
        source_kind="test",
        source_record_type="test",
        source_record_id=1,
    )

    assert contact is not None
    assert contact.organization_id == org_a.id

    with pytest.raises(ValueError, match="organization scope"):
        repo_a.add_contact_if_missing(
            lead_id=lead_b.id,
            contact_type=ContactType.EMAIL,
            raw_value="beta@example.com",
            normalized_value="beta@example.com",
            source_url="https://beta.example",
            source_kind="test",
            source_record_type="test",
            source_record_id=2,
        )


def test_lead_detail_and_contact_sync_stay_child_organization_scoped(db_session) -> None:
    org_a = _organization("scope-a")
    org_b = _organization("scope-b")
    lead = _lead("Casa Escopada", organization=org_a)
    db_session.add_all([org_a, org_b, lead])
    db_session.flush()

    visible_contact = LeadContact(
        organization=org_a,
        lead=lead,
        contact_type=ContactType.EMAIL,
        raw_value="visible@example.com",
        normalized_value="visible@example.com",
        source_kind="test",
        source_record_type="test",
        source_record_id=1,
        confidence=0.5,
    )
    hidden_contact = LeadContact(
        organization=org_b,
        lead=lead,
        contact_type=ContactType.EMAIL,
        raw_value="hidden@example.com",
        normalized_value="hidden@example.com",
        source_kind="test",
        source_record_type="test",
        source_record_id=2,
        confidence=0.99,
    )
    visible_enrichment = LeadEnrichmentRecord(
        organization=org_a,
        lead=lead,
        source_url="https://visible.example",
        extracted_fields={},
        confidence_scores={},
        inferred_material_signals={},
    )
    hidden_enrichment = LeadEnrichmentRecord(
        organization=org_b,
        lead=lead,
        source_url="https://hidden.example",
        extracted_fields={},
        confidence_scores={},
        inferred_material_signals={},
    )
    visible_log = ActivityLog(
        organization=org_a,
        lead=lead,
        entity_type="lead",
        entity_id=lead.id,
        action=ActivityAction.LEAD_UPDATED,
        actor="test",
        metadata_json={},
    )
    hidden_log = ActivityLog(
        organization=org_b,
        lead=lead,
        entity_type="lead",
        entity_id=lead.id,
        action=ActivityAction.LEAD_UPDATED,
        actor="test",
        metadata_json={},
    )
    db_session.add_all(
        [
            visible_contact,
            hidden_contact,
            visible_enrichment,
            hidden_enrichment,
            visible_log,
            hidden_log,
        ]
    )
    db_session.commit()
    db_session.expire_all()

    repo_a = LeadRepository(db_session, organization_id=org_a.id)
    detail = repo_a.get_detail(lead.id)

    assert detail is not None
    assert [contact.raw_value for contact in detail.contacts] == ["visible@example.com"]
    assert [record.source_url for record in detail.enrichments] == ["https://visible.example"]
    assert [log.organization_id for log in detail.activity_logs] == [org_a.id]

    updated_fields = repo_a.sync_canonical_contacts(detail)

    assert updated_fields == ["email"]
    assert detail.email == "visible@example.com"


def test_legacy_default_bridge_sets_child_organization_ids(db_session) -> None:
    default_org = get_or_create_default_organization(db_session)
    legacy_lead = _lead("Legacy Casa", organization=None)
    db_session.add(legacy_lead)
    db_session.commit()

    repository = LeadRepository(db_session)
    contact = repository.add_contact_if_missing(
        lead_id=legacy_lead.id,
        contact_type=ContactType.PHONE,
        raw_value="+5511999999999",
        normalized_value="+5511999999999",
        source_url="https://legacy.example",
        source_kind="test",
        source_record_type="test",
        source_record_id=1,
    )

    assert contact is not None
    assert contact.organization_id == default_org.id

    enrichment_service = EnrichmentService(db_session, _settings())
    enrichment_record = enrichment_service._create_enrichment_record(
        lead=legacy_lead,
        source_url="https://legacy.example",
        page_type="homepage",
        http_status=200,
        robots_allowed=True,
        extracted_fields={},
        confidence_scores={},
        material_signals={},
        note=None,
    )

    assert enrichment_record.organization_id == default_org.id

    CRMService(db_session).update_lead(
        legacy_lead.id,
        LeadUpdateRequest(notes="Bridge note"),
        actor="test",
    )
    activity_logs = db_session.execute(
        select(ActivityLog).where(ActivityLog.lead_id == legacy_lead.id).order_by(ActivityLog.id.asc())
    ).scalars().all()

    assert activity_logs
    assert {log.organization_id for log in activity_logs} == {default_org.id}
