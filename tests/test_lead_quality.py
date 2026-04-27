from __future__ import annotations

from sqlalchemy import inspect

from app.enums import CompanySizeFit, LeadSourceType, LeadStatus, TradeType
from app.models.lead import Lead
from app.models.market_taxonomy import MarketSegment, MarketSubsegment
from app.models.organization import Organization
from app.repositories.lead_repository import LeadRepository
from app.schemas.lead import LeadListFilters, LeadSummary
from app.services.lead_quality import LeadQualityService
from app.services.normalization import normalize_business_name


def _organization() -> Organization:
    return Organization(slug="tenant-a", name="Tenant A", display_name="Tenant A")


def _segment(organization: Organization, key: str, name: str) -> MarketSegment:
    return MarketSegment(organization=organization, key=key, name=name)


def _subsegment(
    organization: Organization,
    segment: MarketSegment,
    key: str,
    name: str,
) -> MarketSubsegment:
    return MarketSubsegment(organization=organization, segment=segment, key=key, name=name)


def _lead(
    business_name: str,
    *,
    organization: Organization,
    category: str = "empresa local",
    city: str | None = "Campinas",
    segment: MarketSegment | None = None,
    subsegment: MarketSubsegment | None = None,
    website: str | None = None,
    email: str | None = None,
    address: str | None = None,
    google_maps_url: str | None = None,
) -> Lead:
    return Lead(
        organization=organization,
        business_name=business_name,
        normalized_business_name=normalize_business_name(business_name) or business_name.lower(),
        category=category,
        city=city,
        state="SP",
        phone="+5511999999999",
        website=website,
        email=email,
        address=address,
        google_maps_url=google_maps_url,
        lead_source_type=LeadSourceType.GOOGLE_PLACES,
        status=LeadStatus.NEW,
        market_segment=segment,
        market_subsegment=subsegment,
    )


def test_lead_quality_columns_and_indexes_are_created(session_factory) -> None:
    engine = session_factory.kw["bind"]
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("leads")}
    indexes = {index["name"] for index in inspector.get_indexes("leads")}

    assert {
        "company_size_fit",
        "company_size_fit_explanation",
        "company_size_fit_metadata_json",
        "trade_type",
        "trade_type_explanation",
        "trade_type_metadata_json",
        "quality_classified_at",
    }.issubset(columns)
    assert {
        "ix_leads_org_company_size_fit",
        "ix_leads_org_trade_type",
    }.issubset(indexes)


def test_lead_quality_classifies_large_enterprise_conservatively(db_session) -> None:
    organization = _organization()
    db_session.add(organization)
    large_lead = _lead(
        "Walmart Campinas",
        organization=organization,
        category="hipermercado",
    )
    local_lead = _lead(
        "Grupo Brasil Consultorio",
        organization=organization,
        category="clinica odontologica",
        website="https://grupobrasil.example.com",
        email="contato@grupobrasil.example.com",
        address="Rua Alpha, 10",
        google_maps_url="https://maps.google.com/?q=Grupo+Brasil+Consultorio",
    )
    db_session.add_all([large_lead, local_lead])
    db_session.commit()

    service = LeadQualityService(db_session, organization_id=organization.id)
    service.apply_batch(lead_ids=[large_lead.id, local_lead.id])
    db_session.refresh(large_lead)
    db_session.refresh(local_lead)

    assert large_lead.company_size_fit == CompanySizeFit.LARGE_ENTERPRISE.value
    assert "walmart" in (large_lead.company_size_fit_explanation or "").lower()
    assert local_lead.company_size_fit == CompanySizeFit.IDEAL_SME.value
    assert local_lead.trade_type == TradeType.UNKNOWN.value


def test_lead_quality_classifies_generic_service_business_from_contact_and_location_evidence(db_session) -> None:
    organization = _organization()
    lead = _lead(
        "Clinica Sorriso",
        organization=organization,
        category="dentista",
        website="https://clinicasorriso.example.com",
        email="contato@clinicasorriso.example.com",
        address="Rua Central, 100",
        google_maps_url="https://maps.google.com/?q=Clinica+Sorriso",
    )
    db_session.add(lead)
    db_session.commit()

    result = LeadQualityService(db_session, organization_id=organization.id).apply_to_lead(lead.id)
    db_session.refresh(lead)
    summary = LeadSummary.model_validate(lead)

    assert lead.company_size_fit == CompanySizeFit.IDEAL_SME.value
    assert lead.trade_type == TradeType.UNKNOWN.value
    assert lead.quality_classified_at is not None
    assert "company_size_fit" in result.changed_fields
    assert summary.company_size_fit == CompanySizeFit.IDEAL_SME
    assert summary.trade_type == TradeType.UNKNOWN


def test_lead_quality_uses_explicit_taxonomy_for_retail_trade_type(db_session) -> None:
    organization = _organization()
    segment = _segment(organization, "varejo", "Varejo")
    subsegment = _subsegment(organization, segment, "loja_de_moveis", "loja de moveis")
    lead = _lead(
        "Loja Bela Casa",
        organization=organization,
        category="loja de moveis",
        segment=segment,
        subsegment=subsegment,
        website="https://belacasa.example.com",
        address="Avenida Moveis, 200",
        google_maps_url="https://maps.google.com/?q=Loja+Bela+Casa",
    )
    db_session.add(lead)
    db_session.commit()

    LeadQualityService(db_session, organization_id=organization.id).apply_to_lead(lead.id)
    db_session.refresh(lead)

    assert lead.company_size_fit == CompanySizeFit.IDEAL_SME.value
    assert lead.trade_type == TradeType.VAREJO.value


def test_lead_quality_distinguishes_atacado_from_distribuidora(db_session) -> None:
    organization = _organization()
    segment = _segment(organization, "atacado_distribuidora", "Atacado/Distribuidora")
    distributor_subsegment = _subsegment(
        organization,
        segment,
        "distribuicao_embalagens",
        "distribuicao de embalagens",
    )
    wholesale_subsegment = _subsegment(
        organization,
        segment,
        "atacado_moveis",
        "atacado de moveis",
    )
    distributor = _lead(
        "Distribuidora Alpha Embalagens",
        organization=organization,
        category="fornecedores de embalagens",
        segment=segment,
        subsegment=distributor_subsegment,
    )
    wholesale = _lead(
        "Atacado Beta Moveis",
        organization=organization,
        category="atacado de moveis",
        segment=segment,
        subsegment=wholesale_subsegment,
    )
    db_session.add_all([distributor, wholesale])
    db_session.commit()

    service = LeadQualityService(db_session, organization_id=organization.id)
    service.apply_batch(lead_ids=[distributor.id, wholesale.id])
    db_session.refresh(distributor)
    db_session.refresh(wholesale)

    assert distributor.trade_type == TradeType.DISTRIBUIDORA.value
    assert wholesale.trade_type == TradeType.ATACADO.value


def test_lead_quality_dry_run_and_repository_filters(db_session) -> None:
    organization = _organization()
    segment = _segment(organization, "varejo", "Varejo")
    subsegment = _subsegment(organization, segment, "loja_de_moveis", "loja de moveis")
    lead = _lead(
        "Moveis Central",
        organization=organization,
        category="loja de moveis",
        segment=segment,
        subsegment=subsegment,
        website="https://moveiscentral.example.com",
        address="Rua das Flores, 50",
        google_maps_url="https://maps.google.com/?q=Moveis+Central",
    )
    db_session.add(lead)
    db_session.commit()

    service = LeadQualityService(db_session, organization_id=organization.id)
    dry_run = service.apply_batch(lead_ids=[lead.id], dry_run=True)
    db_session.refresh(lead)

    assert dry_run.dry_run is True
    assert dry_run.changed == 1
    assert lead.company_size_fit == CompanySizeFit.UNKNOWN.value
    assert lead.trade_type == TradeType.UNKNOWN.value

    service.apply_batch(lead_ids=[lead.id])
    db_session.refresh(lead)
    repository = LeadRepository(db_session, organization_id=organization.id)
    fit_matches, fit_total = repository.list_leads(LeadListFilters(company_size_fit=CompanySizeFit.IDEAL_SME))
    trade_matches, trade_total = repository.list_leads(LeadListFilters(trade_type=TradeType.VAREJO))

    assert fit_total == 1
    assert fit_matches[0].id == lead.id
    assert trade_total == 1
    assert trade_matches[0].id == lead.id


def test_lead_quality_preserves_existing_values_without_overwrite(db_session) -> None:
    organization = _organization()
    lead = _lead("Walmart Campinas", organization=organization, category="hipermercado")
    lead.company_size_fit = CompanySizeFit.IDEAL_SME.value
    lead.company_size_fit_explanation = "Manual review."
    db_session.add(lead)
    db_session.commit()

    LeadQualityService(db_session, organization_id=organization.id).apply_to_lead(lead.id, overwrite=False)
    db_session.refresh(lead)

    assert lead.company_size_fit == CompanySizeFit.IDEAL_SME.value
    assert lead.company_size_fit_explanation == "Manual review."

    LeadQualityService(db_session, organization_id=organization.id).apply_to_lead(lead.id, overwrite=True)
    db_session.refresh(lead)

    assert lead.company_size_fit == CompanySizeFit.LARGE_ENTERPRISE.value
    assert "walmart" in (lead.company_size_fit_explanation or "").lower()
