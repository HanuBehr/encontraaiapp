from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.assignment_rule import AssignmentRule
from app.models.market_taxonomy import MarketSegment, MarketSubsegment
from app.models.organization import Organization
from app.models.sales_region import SalesRegion
from app.models.sales_rep import SalesRep
from app.repositories.organization_repository import (
    OrganizationRepository,
    get_or_create_default_organization,
)


GARIN_SALES_REP_NAMES = (
    "Willian",
    "Gleicy",
    "Sueli",
    "Marta",
    "Thayná",
    "Cintia",
    "Jackson",
    "Vendas2",
)

GARIN_REGION_NAMES = (
    "São Paulo – Zona Norte",
    "São Paulo – Zona Leste",
    "São Paulo – Zona Sul",
    "São Paulo – Zona Oeste",
    "Macro Metropolitana Paulista",
    "Litoral Sul Paulista",
    "Campinas",
    "Vale do Paraíba Paulista",
    "Ribeirão Preto",
    "Araraquara",
    "Piracicaba",
    "Presidente Prudente",
    "Bauru",
    "Araçatuba",
    "Assis",
    "Marília",
    "São José do Rio Preto",
)

CONSTRUCTION_SPLIT = {
    "Willian": (
        "São Paulo – Zona Norte",
        "São Paulo – Zona Leste",
        "Litoral Sul Paulista",
        "Campinas",
        "Vale do Paraíba Paulista",
        "Ribeirão Preto",
        "Araraquara",
        "Piracicaba",
        "Presidente Prudente",
    ),
    "Gleicy": (
        "São Paulo – Zona Sul",
        "São Paulo – Zona Oeste",
        "Macro Metropolitana Paulista",
        "Bauru",
        "Araçatuba",
        "Assis",
        "Marília",
        "São José do Rio Preto",
    ),
}

COMMERCIAL_SPLIT = {
    "Marta": (
        "São Paulo – Zona Norte",
        "Vale do Paraíba Paulista",
        "Ribeirão Preto",
        "Piracicaba",
    ),
    "Thayná": (
        "São Paulo – Zona Leste",
        "Araraquara",
        "Bauru",
    ),
    "Cintia": (
        "São Paulo – Zona Sul",
        "Macro Metropolitana Paulista",
        "Litoral Sul Paulista",
    ),
    "Jackson": (
        "São Paulo – Zona Oeste",
        "Presidente Prudente",
        "Assis",
    ),
    "Vendas2": (
        "Campinas",
        "Araçatuba",
        "Marília",
    ),
}


@dataclass(frozen=True, slots=True)
class RegionSeed:
    name: str
    code: str
    cities: tuple[str, ...]
    postal_code_prefixes: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SegmentSeed:
    key: str
    name: str
    sort_order: int
    description: str | None = None


@dataclass(frozen=True, slots=True)
class SubsegmentSeed:
    key: str
    name: str
    segment_key: str
    keywords: tuple[str, ...]
    sort_order: int
    description: str | None = None


@dataclass(frozen=True, slots=True)
class GarinBootstrapResult:
    organization_id: int
    organization_slug: str
    sales_reps: int
    sales_regions: int
    market_segments: int
    market_subsegments: int
    assignment_rules: int
    warnings: tuple[str, ...] = ()


SP_ZONE_NORTH_NEIGHBORHOODS = (
    "Santana",
    "Tucuruvi",
    "Vila Maria",
    "Vila Guilherme",
    "Casa Verde",
    "Freguesia do Ó",
    "Brasilândia",
    "Jaçanã",
    "Tremembé",
    "Mandaqui",
    "Limão",
    "Cachoeirinha",
    "Perus",
    "Pirituba",
)

SP_ZONE_EAST_NEIGHBORHOODS = (
    "Tatuapé",
    "Mooca",
    "Penha",
    "Itaquera",
    "São Mateus",
    "São Miguel Paulista",
    "Ermelino Matarazzo",
    "Guaianases",
    "Cidade Tiradentes",
    "Aricanduva",
    "Vila Formosa",
    "Vila Prudente",
    "Sapopemba",
    "Belém",
    "Brás",
)

SP_ZONE_SOUTH_NEIGHBORHOODS = (
    "Santo Amaro",
    "Jabaquara",
    "Campo Limpo",
    "Capão Redondo",
    "Cidade Ademar",
    "Grajaú",
    "Interlagos",
    "Socorro",
    "Parelheiros",
    "Moema",
    "Vila Mariana",
    "Saúde",
    "Ipiranga",
)

SP_ZONE_WEST_NEIGHBORHOODS = (
    "Pinheiros",
    "Lapa",
    "Butantã",
    "Perdizes",
    "Vila Leopoldina",
    "Alto de Pinheiros",
    "Jaguaré",
    "Raposo Tavares",
    "Morumbi",
    "Itaim Bibi",
    "Jardins",
)


REGION_SEEDS = (
    RegionSeed(
        name="São Paulo – Zona Norte",
        code="sp-zona-norte",
        cities=("São Paulo",),
        postal_code_prefixes=("020", "021", "022", "023", "024", "025", "026", "027", "028", "029"),
        metadata={
            "requires_neighborhood_match": True,
            "neighborhood_keywords": SP_ZONE_NORTH_NEIGHBORHOODS,
        },
    ),
    RegionSeed(
        name="São Paulo – Zona Leste",
        code="sp-zona-leste",
        cities=("São Paulo",),
        postal_code_prefixes=(
            "030",
            "031",
            "032",
            "033",
            "034",
            "035",
            "036",
            "037",
            "038",
            "039",
            "080",
            "081",
            "082",
            "083",
            "084",
            "085",
        ),
        metadata={
            "requires_neighborhood_match": True,
            "neighborhood_keywords": SP_ZONE_EAST_NEIGHBORHOODS,
        },
    ),
    RegionSeed(
        name="São Paulo – Zona Sul",
        code="sp-zona-sul",
        cities=("São Paulo",),
        postal_code_prefixes=("040", "041", "042", "043", "044", "045", "046", "047", "048", "049", "057", "058"),
        metadata={
            "requires_neighborhood_match": True,
            "neighborhood_keywords": SP_ZONE_SOUTH_NEIGHBORHOODS,
        },
    ),
    RegionSeed(
        name="São Paulo – Zona Oeste",
        code="sp-zona-oeste",
        cities=("São Paulo",),
        postal_code_prefixes=("050", "051", "052", "053", "054", "055", "056"),
        metadata={
            "requires_neighborhood_match": True,
            "neighborhood_keywords": SP_ZONE_WEST_NEIGHBORHOODS,
        },
    ),
    RegionSeed(
        name="Macro Metropolitana Paulista",
        code="sp-macro-metropolitana-paulista",
        cities=(
            "Guarulhos",
            "Osasco",
            "Barueri",
            "Carapicuíba",
            "Cotia",
            "Jundiaí",
            "Sorocaba",
            "Mogi das Cruzes",
            "Santo André",
            "São Bernardo do Campo",
            "São Caetano do Sul",
            "Diadema",
            "Mauá",
        ),
    ),
    RegionSeed(
        name="Litoral Sul Paulista",
        code="sp-litoral-sul-paulista",
        cities=(
            "Santos",
            "São Vicente",
            "Praia Grande",
            "Guarujá",
            "Cubatão",
            "Itanhaém",
            "Peruíbe",
            "Mongaguá",
            "Registro",
            "Iguape",
        ),
    ),
    RegionSeed(
        name="Campinas",
        code="sp-campinas",
        cities=(
            "Campinas",
            "Americana",
            "Sumaré",
            "Hortolândia",
            "Indaiatuba",
            "Paulínia",
            "Valinhos",
            "Vinhedo",
            "Limeira",
            "Mogi Guaçu",
        ),
    ),
    RegionSeed(
        name="Vale do Paraíba Paulista",
        code="sp-vale-do-paraiba-paulista",
        cities=(
            "São José dos Campos",
            "Taubaté",
            "Jacareí",
            "Caçapava",
            "Guaratinguetá",
            "Lorena",
            "Cruzeiro",
            "Pindamonhangaba",
            "Caraguatatuba",
            "Ubatuba",
        ),
    ),
    RegionSeed(
        name="Ribeirão Preto",
        code="sp-ribeirao-preto",
        cities=("Ribeirão Preto", "Sertãozinho", "Bebedouro", "Jaboticabal", "Franca", "Batatais"),
    ),
    RegionSeed(
        name="Araraquara",
        code="sp-araraquara",
        cities=("Araraquara", "São Carlos", "Matão", "Ibitinga"),
    ),
    RegionSeed(
        name="Piracicaba",
        code="sp-piracicaba",
        cities=("Piracicaba", "Rio Claro", "Santa Bárbara d'Oeste"),
    ),
    RegionSeed(
        name="Presidente Prudente",
        code="sp-presidente-prudente",
        cities=("Presidente Prudente", "Adamantina", "Dracena", "Presidente Venceslau"),
    ),
    RegionSeed(
        name="Bauru",
        code="sp-bauru",
        cities=("Bauru", "Botucatu", "Jaú", "Lençóis Paulista", "Avaré", "Lins"),
    ),
    RegionSeed(
        name="Araçatuba",
        code="sp-aracatuba",
        cities=("Araçatuba", "Birigui", "Penápolis", "Andradina"),
    ),
    RegionSeed(
        name="Assis",
        code="sp-assis",
        cities=("Assis", "Ourinhos", "Palmital", "Paraguaçu Paulista"),
    ),
    RegionSeed(
        name="Marília",
        code="sp-marilia",
        cities=("Marília", "Tupã", "Garça"),
    ),
    RegionSeed(
        name="São José do Rio Preto",
        code="sp-sao-jose-do-rio-preto",
        cities=(
            "São José do Rio Preto",
            "Catanduva",
            "Votuporanga",
            "Fernandópolis",
            "Jales",
            "Mirassol",
            "Olímpia",
        ),
    ),
)

SEGMENT_SEEDS = (
    SegmentSeed("varejo", "Varejo", 10),
    SegmentSeed("atacado_distribuidora", "Atacado/Distribuidora", 20),
    SegmentSeed("construcao_civil", "Construção Civil", 30),
    SegmentSeed("industria", "Indústria", 40),
    SegmentSeed("e_commerce", "E-commerce", 50),
)

SUBSEGMENT_SEEDS = (
    SubsegmentSeed(
        "distribuidoras_materiais_construcao",
        "distribuidoras de materiais de construção",
        "atacado_distribuidora",
        (
            "distribuidora de materiais de construção",
            "distribuidora de material de construção",
            "distribuidora materiais construção",
        ),
        10,
    ),
    SubsegmentSeed(
        "distribuidoras_tintas",
        "distribuidoras de tintas",
        "atacado_distribuidora",
        ("distribuidora de tintas", "distribuição de tintas", "atacado de tintas"),
        20,
    ),
    SubsegmentSeed(
        "atacado_ferragens",
        "atacado de ferragens",
        "atacado_distribuidora",
        ("atacado de ferragens", "distribuidora de ferragens", "ferragens atacado"),
        30,
    ),
    SubsegmentSeed(
        "ecommerce_materiais_construcao",
        "e-commerce de materiais de construção",
        "e_commerce",
        (
            "e-commerce de materiais de construção",
            "ecommerce de materiais de construção",
            "loja online de materiais de construção",
        ),
        40,
    ),
    SubsegmentSeed(
        "marketplace_loja_virtual",
        "marketplace / loja virtual",
        "e_commerce",
        ("marketplace", "loja virtual", "e-commerce", "ecommerce"),
        50,
    ),
    SubsegmentSeed(
        "construtoras",
        "construtoras",
        "construcao_civil",
        ("construtora", "construtoras", "construção civil"),
        60,
    ),
    SubsegmentSeed(
        "incorporadoras",
        "incorporadoras",
        "construcao_civil",
        ("incorporadora", "incorporadoras", "incorporação imobiliária"),
        70,
    ),
    SubsegmentSeed(
        "aplicadores_impermeabilizacao",
        "aplicadores de impermeabilização",
        "construcao_civil",
        ("impermeabilização", "impermeabilizante", "aplicador de impermeabilização"),
        80,
    ),
    SubsegmentSeed(
        "materiais_construcao",
        "materiais de construção",
        "varejo",
        (
            "materiais de construção",
            "material de construção",
            "loja de material de construção",
            "casa de material de construção",
        ),
        90,
    ),
    SubsegmentSeed(
        "ferragistas",
        "ferragistas",
        "varejo",
        ("ferragista", "ferragistas", "loja de ferragens", "casa de ferragens"),
        100,
    ),
    SubsegmentSeed(
        "loja_de_tintas",
        "loja de tintas",
        "varejo",
        ("loja de tintas", "casa de tintas"),
        110,
    ),
    SubsegmentSeed(
        "vidraceiros",
        "vidraceiros",
        "varejo",
        ("vidraceiro", "vidraceiros", "vidraçaria", "vidracaria"),
        120,
    ),
    SubsegmentSeed(
        "marmorarias",
        "marmorarias",
        "varejo",
        ("marmoraria", "marmorarias", "mármore", "granito"),
        130,
    ),
    SubsegmentSeed(
        "refrigeracao",
        "refrigeração",
        "varejo",
        ("refrigeração", "climatização", "ar condicionado"),
        140,
    ),
    SubsegmentSeed(
        "industria_textil",
        "indústria têxtil",
        "industria",
        ("indústria têxtil", "industria textil", "confecção", "tecelagem"),
        150,
    ),
    SubsegmentSeed(
        "industria_moveleira",
        "indústria moveleira",
        "industria",
        ("indústria moveleira", "industria moveleira", "fábrica de móveis", "moveleira"),
        160,
    ),
    SubsegmentSeed(
        "industria_metalurgica",
        "indústria metalúrgica",
        "industria",
        ("indústria metalúrgica", "industria metalurgica", "metalúrgica", "metalurgica"),
        170,
    ),
    SubsegmentSeed(
        "industria_quimica",
        "indústria química",
        "industria",
        ("indústria química", "industria quimica", "química industrial", "produtos químicos"),
        180,
    ),
)


def bootstrap_garin_configuration(db: Session, *, organization_slug: str | None = None) -> GarinBootstrapResult:
    organization = _resolve_organization(db, organization_slug=organization_slug)
    reps = {
        name: _upsert_sales_rep(db, organization=organization, name=name)
        for name in GARIN_SALES_REP_NAMES
    }
    regions = {
        seed.name: _upsert_sales_region(db, organization=organization, seed=seed)
        for seed in REGION_SEEDS
    }
    segments = {
        seed.key: _upsert_segment(db, organization=organization, seed=seed)
        for seed in SEGMENT_SEEDS
    }
    subsegments = [
        _upsert_subsegment(
            db,
            organization=organization,
            seed=seed,
            segment=segments[seed.segment_key],
        )
        for seed in SUBSEGMENT_SEEDS
    ]
    rules = _upsert_assignment_rules(
        db,
        organization=organization,
        reps=reps,
        regions=regions,
        segments=segments,
    )
    db.flush()

    return GarinBootstrapResult(
        organization_id=organization.id,
        organization_slug=organization.slug,
        sales_reps=len(reps),
        sales_regions=len(regions),
        market_segments=len(segments),
        market_subsegments=len(subsegments),
        assignment_rules=len(rules),
        warnings=tuple(_bootstrap_warnings()),
    )


def _resolve_organization(db: Session, *, organization_slug: str | None) -> Organization:
    if not organization_slug:
        return get_or_create_default_organization(db)

    repository = OrganizationRepository(db)
    organization = repository.get_by_slug(organization_slug)
    if organization is not None:
        return organization

    display_name = "Garin" if organization_slug == "garin" else organization_slug.replace("-", " ").title()
    organization = Organization(slug=organization_slug, name=display_name, display_name=display_name)
    db.add(organization)
    db.flush()
    return organization


def _upsert_sales_rep(db: Session, *, organization: Organization, name: str) -> SalesRep:
    external_ref = f"garin:{name.casefold()}"
    rep = db.execute(
        select(SalesRep).where(
            SalesRep.organization_id == organization.id,
            SalesRep.external_ref == external_ref,
        )
    ).scalar_one_or_none()
    if rep is None:
        rep = db.execute(
            select(SalesRep).where(
                SalesRep.organization_id == organization.id,
                func.lower(SalesRep.name) == name.lower(),
            )
        ).scalar_one_or_none()
    if rep is None:
        rep = SalesRep(organization_id=organization.id, name=name)
        db.add(rep)

    rep.name = name
    rep.external_ref = external_ref
    rep.is_active = True
    rep.metadata_json = {
        **(rep.metadata_json or {}),
        "source": "garin_bootstrap",
    }
    return rep


def _upsert_sales_region(db: Session, *, organization: Organization, seed: RegionSeed) -> SalesRegion:
    region = db.execute(
        select(SalesRegion).where(
            SalesRegion.organization_id == organization.id,
            SalesRegion.code == seed.code,
        )
    ).scalar_one_or_none()
    if region is None:
        region = db.execute(
            select(SalesRegion).where(
                SalesRegion.organization_id == organization.id,
                SalesRegion.region_type == "mesoregion",
                SalesRegion.name == seed.name,
            )
        ).scalar_one_or_none()
    if region is None:
        region = SalesRegion(organization_id=organization.id, name=seed.name, region_type="mesoregion")
        db.add(region)

    region.name = seed.name
    region.region_type = "mesoregion"
    region.state = "SP"
    region.code = seed.code
    region.cities_json = list(seed.cities)
    region.postal_codes_json = list(seed.postal_code_prefixes)
    region.metadata_json = {
        **seed.metadata,
        "source": "garin_bootstrap",
    }
    region.is_active = True
    return region


def _upsert_segment(db: Session, *, organization: Organization, seed: SegmentSeed) -> MarketSegment:
    segment = db.execute(
        select(MarketSegment).where(
            MarketSegment.organization_id == organization.id,
            MarketSegment.key == seed.key,
        )
    ).scalar_one_or_none()
    if segment is None:
        segment = MarketSegment(organization_id=organization.id, key=seed.key, name=seed.name)
        db.add(segment)

    segment.name = seed.name
    segment.description = seed.description
    segment.sort_order = seed.sort_order
    segment.is_active = True
    return segment


def _upsert_subsegment(
    db: Session,
    *,
    organization: Organization,
    seed: SubsegmentSeed,
    segment: MarketSegment,
) -> MarketSubsegment:
    subsegment = db.execute(
        select(MarketSubsegment).where(
            MarketSubsegment.organization_id == organization.id,
            MarketSubsegment.key == seed.key,
        )
    ).scalar_one_or_none()
    if subsegment is None:
        subsegment = MarketSubsegment(
            organization_id=organization.id,
            segment=segment,
            key=seed.key,
            name=seed.name,
        )
        db.add(subsegment)

    subsegment.segment = segment
    subsegment.name = seed.name
    subsegment.description = seed.description
    subsegment.keywords_json = list(seed.keywords)
    subsegment.sort_order = seed.sort_order
    subsegment.is_active = True
    return subsegment


def _upsert_assignment_rules(
    db: Session,
    *,
    organization: Organization,
    reps: dict[str, SalesRep],
    regions: dict[str, SalesRegion],
    segments: dict[str, MarketSegment],
) -> list[AssignmentRule]:
    rules: list[AssignmentRule] = []
    for priority, (rep_name, region_names) in enumerate(_split_items(CONSTRUCTION_SPLIT), start=100):
        for region_name in region_names:
            rules.append(
                _upsert_assignment_rule(
                    db,
                    organization=organization,
                    name=f"Construção Civil - {rep_name} - {region_name}",
                    priority=priority,
                    sales_rep=reps[rep_name],
                    sales_region=regions[region_name],
                    market_segment=segments["construcao_civil"],
                )
            )

    rules.append(
        _upsert_assignment_rule(
            db,
            organization=organization,
            name="Indústria - Sueli - Todos os territórios",
            priority=200,
            sales_rep=reps["Sueli"],
            sales_region=None,
            market_segment=segments["industria"],
        )
    )

    commercial_segments = ("varejo", "atacado_distribuidora", "e_commerce")
    for segment_offset, segment_key in enumerate(commercial_segments, start=0):
        segment = segments[segment_key]
        for split_offset, (rep_name, region_names) in enumerate(_split_items(COMMERCIAL_SPLIT), start=0):
            for region_index, region_name in enumerate(region_names, start=1):
                priority = 300 + (segment_offset * 100) + (split_offset * 10) + region_index
                rules.append(
                    _upsert_assignment_rule(
                        db,
                        organization=organization,
                        name=f"{segment.name} - {rep_name} - {region_name}",
                        priority=priority,
                        sales_rep=reps[rep_name],
                        sales_region=regions[region_name],
                        market_segment=segment,
                    )
                )
    return rules


def _upsert_assignment_rule(
    db: Session,
    *,
    organization: Organization,
    name: str,
    priority: int,
    sales_rep: SalesRep,
    sales_region: SalesRegion | None,
    market_segment: MarketSegment,
) -> AssignmentRule:
    rule = db.execute(
        select(AssignmentRule).where(
            AssignmentRule.organization_id == organization.id,
            AssignmentRule.name == name,
        )
    ).scalar_one_or_none()
    if rule is None:
        rule = AssignmentRule(organization_id=organization.id, name=name, sales_rep=sales_rep)
        db.add(rule)

    rule.name = name
    rule.priority = priority
    rule.sales_rep = sales_rep
    rule.sales_region = sales_region
    rule.market_segment = market_segment
    rule.market_subsegment = None
    rule.conditions_json = {
        "schema_version": 1,
        "source": "garin_bootstrap",
        "region": sales_region.name if sales_region else None,
        "segment_key": market_segment.key,
    }
    rule.is_active = True
    return rule


def _split_items(split: dict[str, tuple[str, ...]]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    return tuple(split.items())


def _bootstrap_warnings() -> list[str]:
    commercial_regions = {
        region_name
        for region_names in COMMERCIAL_SPLIT.values()
        for region_name in region_names
    }
    missing_commercial_regions = [
        region_name
        for region_name in GARIN_REGION_NAMES
        if region_name not in commercial_regions
    ]
    if not missing_commercial_regions:
        return []
    return [
        "No Varejo/Atacado/E-commerce owner was provided for: "
        + ", ".join(missing_commercial_regions)
        + ". The bootstrap leaves those segment-region routes unassigned."
    ]
