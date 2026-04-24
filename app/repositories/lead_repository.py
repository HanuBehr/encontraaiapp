from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session, selectinload, with_loader_criteria

from app.enums import ContactType, ImportBatchStatus
from app.models.activity_log import ActivityLog
from app.models.import_batch import ImportBatch
from app.models.lead import Lead
from app.models.lead_contact import LeadContact
from app.models.lead_enrichment_record import LeadEnrichmentRecord
from app.models.market_taxonomy import MarketSegment, MarketSubsegment
from app.models.raw_discovery_record import RawDiscoveryRecord
from app.models.sales_region import SalesRegion
from app.models.sales_rep import SalesRep
from app.repositories.organization_repository import get_or_create_default_organization
from app.schemas.discovery import DiscoveryLeadCandidate
from app.schemas.lead import LeadBlockedFilter, LeadListFilters
from app.services.normalization import normalize_brazilian_state


CONTACT_FIELD_MAP: dict[ContactType, str] = {
    ContactType.EMAIL: "email",
    ContactType.PHONE: "phone",
    ContactType.WHATSAPP: "whatsapp",
    ContactType.INSTAGRAM: "instagram",
}

LEAD_SORT_COLUMNS = {
    "id": Lead.id,
    "business_name": Lead.business_name,
    "city": Lead.city,
    "state": Lead.state,
    "status": Lead.status,
    "lead_score": Lead.lead_score,
    "created_at": Lead.created_at,
    "updated_at": Lead.updated_at,
    "last_enriched_at": Lead.last_enriched_at,
    "assigned_at": Lead.assigned_at,
    "company_size_fit": Lead.company_size_fit,
    "trade_type": Lead.trade_type,
}


class LeadRepository:
    def __init__(self, db: Session, organization_id: int | None = None) -> None:
        self.db = db
        self._organization_id = organization_id
        self._include_unassigned_leads = organization_id is None

    @property
    def organization_id(self) -> int:
        if self._organization_id is None:
            self._organization_id = get_or_create_default_organization(self.db).id
        return self._organization_id

    def list_leads(self, filters: LeadListFilters) -> tuple[list[Lead], int]:
        conditions = self._build_filter_conditions(filters)
        total = self.db.execute(select(func.count(Lead.id)).where(*conditions)).scalar_one()
        query = (
            select(Lead)
            .options(*self._assignment_loader_options())
            .where(*conditions)
            .order_by(*self._sort_expressions(filters))
            .offset(filters.offset)
            .limit(filters.limit)
        )
        leads = self.db.execute(query).scalars().all()
        return leads, total

    def list_all_leads(self, filters: LeadListFilters | None = None) -> list[Lead]:
        filters = filters or LeadListFilters()
        conditions = self._build_filter_conditions(filters)
        query = (
            select(Lead)
            .options(*self._export_loader_options())
            .where(*conditions)
            .order_by(*self._sort_expressions(filters))
        )
        return self.db.execute(query).scalars().all()

    def list_lead_ids(self, filters: LeadListFilters | None = None) -> list[int]:
        filters = filters or LeadListFilters()
        query = (
            select(Lead.id)
            .where(*self._build_filter_conditions(filters))
            .order_by(*self._sort_expressions(filters))
        )
        return [int(lead_id) for lead_id in self.db.execute(query).scalars().all()]

    def get_by_id(self, lead_id: int) -> Lead | None:
        query = select(Lead).where(Lead.id == lead_id, *self._organization_conditions())
        return self.db.execute(query).scalar_one_or_none()

    def get_detail(self, lead_id: int) -> Lead | None:
        query = (
            select(Lead)
            .options(
                *self._assignment_loader_options(),
                selectinload(Lead.contacts),
                selectinload(Lead.enrichments),
                selectinload(Lead.activity_logs),
                selectinload(Lead.raw_discovery_records),
                selectinload(Lead.outreach_drafts),
                *self._tenant_child_loader_options(),
            )
            .where(Lead.id == lead_id, *self._organization_conditions())
        )
        lead = self.db.execute(query).scalar_one_or_none()
        if lead is None:
            return None

        lead.contacts.sort(key=lambda item: (not item.is_primary, item.contact_type.value, -item.confidence, item.id))
        lead.enrichments.sort(key=lambda item: item.fetched_at, reverse=True)
        lead.activity_logs.sort(key=lambda item: item.created_at, reverse=True)
        return lead

    def get_with_related(self, lead_id: int) -> Lead | None:
        query = (
            select(Lead)
            .options(
                *self._assignment_loader_options(),
                selectinload(Lead.contacts),
                selectinload(Lead.enrichments),
                selectinload(Lead.raw_discovery_records),
                selectinload(Lead.outreach_drafts),
                selectinload(Lead.activity_logs),
                *self._tenant_child_loader_options(),
            )
            .where(Lead.id == lead_id, *self._organization_conditions())
        )
        return self.db.execute(query).scalar_one_or_none()

    def get_by_ids(self, lead_ids: Iterable[int]) -> list[Lead]:
        normalized_ids = list(dict.fromkeys(lead_ids))
        if not normalized_ids:
            return []
        query = (
            select(Lead)
            .options(
                *self._assignment_loader_options(),
                selectinload(Lead.contacts),
                selectinload(Lead.enrichments),
                selectinload(Lead.raw_discovery_records),
                *self._tenant_child_loader_options(),
            )
            .where(Lead.id.in_(normalized_ids), *self._organization_conditions())
            .order_by(Lead.id.asc())
        )
        return self.db.execute(query).scalars().all()

    def list_export_leads_by_ids(
        self,
        lead_ids: Iterable[int],
        *,
        blocked: LeadBlockedFilter = "exclude",
    ) -> list[Lead]:
        normalized_ids = list(dict.fromkeys(int(lead_id) for lead_id in lead_ids))
        if not normalized_ids:
            return []
        conditions: list[object] = [
            Lead.id.in_(normalized_ids),
            *self._organization_conditions(),
            *self._blocked_conditions(blocked),
        ]
        query = (
            select(Lead)
            .options(*self._export_loader_options())
            .where(*conditions)
            .execution_options(populate_existing=True)
        )
        leads = self.db.execute(query).scalars().all()
        order = {lead_id: index for index, lead_id in enumerate(normalized_ids)}
        return sorted(leads, key=lambda lead: order.get(lead.id, len(order)))

    def list_recent_import_batches(
        self,
        limit: int = 25,
        *,
        blocked: LeadBlockedFilter = "exclude",
    ) -> list[ImportBatch]:
        query = (
            select(ImportBatch)
            .join(RawDiscoveryRecord, RawDiscoveryRecord.import_batch_id == ImportBatch.id)
            .join(Lead, RawDiscoveryRecord.lead_id == Lead.id)
            .where(
                ImportBatch.status == ImportBatchStatus.COMPLETED,
                RawDiscoveryRecord.lead_id.is_not(None),
                *self._organization_conditions(),
                *self._blocked_conditions(blocked),
            )
            .distinct()
            .order_by(ImportBatch.completed_at.desc(), ImportBatch.id.desc())
            .limit(limit)
        )
        return self.db.execute(query).scalars().all()

    def get_latest_completed_import_batch(
        self,
        *,
        blocked: LeadBlockedFilter = "exclude",
    ) -> ImportBatch | None:
        batches = self.list_recent_import_batches(limit=1, blocked=blocked)
        return batches[0] if batches else None

    def get_completed_import_batch(self, batch_id: int) -> ImportBatch | None:
        query = select(ImportBatch).where(
            ImportBatch.id == batch_id,
            ImportBatch.status == ImportBatchStatus.COMPLETED,
        )
        return self.db.execute(query).scalar_one_or_none()

    def list_lead_ids_for_import_batch(
        self,
        batch_id: int,
        *,
        blocked: LeadBlockedFilter = "exclude",
    ) -> list[int]:
        query = (
            select(RawDiscoveryRecord.lead_id)
            .join(Lead, RawDiscoveryRecord.lead_id == Lead.id)
            .where(
                RawDiscoveryRecord.import_batch_id == batch_id,
                RawDiscoveryRecord.lead_id.is_not(None),
                *self._organization_conditions(),
                *self._blocked_conditions(blocked),
            )
            .order_by(RawDiscoveryRecord.created_at.asc(), RawDiscoveryRecord.id.asc())
        )
        lead_ids = self.db.execute(query).scalars().all()
        return [int(lead_id) for lead_id in dict.fromkeys(lead_ids) if lead_id is not None]

    def list_distinct_cities(self) -> list[str]:
        query = (
            select(Lead.city)
            .where(Lead.city.is_not(None), *self._organization_conditions(), *self._blocked_conditions("exclude"))
            .distinct()
            .order_by(Lead.city.asc())
        )
        return [value for value in self.db.execute(query).scalars().all() if value]

    def list_distinct_states(self) -> list[str]:
        query = (
            select(Lead.state)
            .where(Lead.state.is_not(None), *self._organization_conditions(), *self._blocked_conditions("exclude"))
            .distinct()
            .order_by(Lead.state.asc())
        )
        return [value for value in self.db.execute(query).scalars().all() if value]

    def list_distinct_categories(self) -> list[str]:
        query = (
            select(Lead.category)
            .where(Lead.category.is_not(None), *self._organization_conditions(), *self._blocked_conditions("exclude"))
            .distinct()
            .order_by(Lead.category.asc())
        )
        return [value for value in self.db.execute(query).scalars().all() if value]

    def list_assignment_filter_options(self) -> dict[str, list[tuple[int, str]]]:
        return {
            "sales_reps": self._assignment_options(SalesRep, Lead.assigned_sales_rep_id),
            "sales_regions": self._assignment_options(SalesRegion, Lead.sales_region_id),
            "market_segments": self._assignment_options(MarketSegment, Lead.market_segment_id),
            "market_subsegments": self._assignment_options(MarketSubsegment, Lead.market_subsegment_id),
        }

    def list_v2_filter_options(self) -> dict[str, list[dict[str, object]]]:
        organization_id = self.organization_id
        sales_reps = self.db.execute(
            select(SalesRep)
            .where(SalesRep.organization_id == organization_id, SalesRep.is_active.is_(True))
            .order_by(SalesRep.name.asc(), SalesRep.id.asc())
        ).scalars().all()
        sales_regions = self.db.execute(
            select(SalesRegion)
            .where(SalesRegion.organization_id == organization_id, SalesRegion.is_active.is_(True))
            .order_by(SalesRegion.name.asc(), SalesRegion.id.asc())
        ).scalars().all()
        market_segments = self.db.execute(
            select(MarketSegment)
            .where(MarketSegment.organization_id == organization_id, MarketSegment.is_active.is_(True))
            .order_by(MarketSegment.sort_order.asc(), MarketSegment.name.asc(), MarketSegment.id.asc())
        ).scalars().all()
        market_subsegments = self.db.execute(
            select(MarketSubsegment)
            .where(MarketSubsegment.organization_id == organization_id, MarketSubsegment.is_active.is_(True))
            .order_by(MarketSubsegment.sort_order.asc(), MarketSubsegment.name.asc(), MarketSubsegment.id.asc())
        ).scalars().all()
        return {
            "assigned_reps": [{"id": rep.id, "name": rep.name} for rep in sales_reps],
            "sales_regions": [
                {
                    "id": region.id,
                    "name": region.name,
                    "region_type": region.region_type,
                    "state": region.state,
                    "code": region.code,
                }
                for region in sales_regions
            ],
            "market_segments": [
                {"id": segment.id, "key": segment.key, "name": segment.name}
                for segment in market_segments
            ],
            "market_subsegments": [
                {
                    "id": subsegment.id,
                    "key": subsegment.key,
                    "name": subsegment.name,
                    "market_segment_id": subsegment.segment_id,
                }
                for subsegment in market_subsegments
            ],
        }

    def get_overview_snapshot(self, recent_limit: int = 10) -> tuple[dict[str, int], list[Lead]]:
        conditions = [*self._organization_conditions(), *self._blocked_conditions("exclude")]
        metrics_query = select(
            func.count(Lead.id).label("total"),
            func.coalesce(
                func.sum(case((and_(Lead.email.is_not(None), Lead.email != ""), 1), else_=0)),
                0,
            ).label("with_email"),
            func.coalesce(
                func.sum(case((and_(Lead.whatsapp.is_not(None), Lead.whatsapp != ""), 1), else_=0)),
                0,
            ).label("with_whatsapp"),
            func.coalesce(
                func.sum(case((Lead.do_not_contact.is_(True), 1), else_=0)),
                0,
            ).label("do_not_contact"),
        ).where(*conditions)
        metrics_row = self.db.execute(metrics_query).one()
        recent_query = (
            select(Lead)
            .options(*self._assignment_loader_options())
            .where(*conditions)
            .order_by(Lead.updated_at.desc(), Lead.id.desc())
            .limit(recent_limit)
        )
        recent_leads = self.db.execute(recent_query).scalars().all()
        return (
            {
                "total": int(metrics_row.total or 0),
                "with_email": int(metrics_row.with_email or 0),
                "with_whatsapp": int(metrics_row.with_whatsapp or 0),
                "do_not_contact": int(metrics_row.do_not_contact or 0),
            },
            recent_leads,
        )

    def upsert_from_discovery(self, candidate: DiscoveryLeadCandidate) -> tuple[Lead, bool]:
        lead = self._find_existing(candidate)
        created = lead is None
        normalized_state = normalize_brazilian_state(candidate.state) or candidate.state

        if lead is None:
            lead = Lead(
                business_name=candidate.business_name,
                normalized_business_name=candidate.normalized_business_name,
                category=candidate.category,
                address=candidate.address,
                neighborhood=candidate.neighborhood,
                city=candidate.city,
                state=normalized_state,
                postal_code=candidate.postal_code,
                latitude=candidate.latitude,
                longitude=candidate.longitude,
                website=candidate.website,
                domain=candidate.domain,
                email=candidate.email,
                phone=candidate.phone,
                whatsapp=candidate.whatsapp,
                instagram=candidate.instagram,
                google_maps_url=candidate.google_maps_url,
                google_place_id=candidate.google_place_id,
                source_provider=candidate.source_provider,
                source_url=candidate.source_url,
                lead_source_type=candidate.lead_source_type,
                organization_id=self.organization_id,
            )
            self.db.add(lead)
            self.db.flush()
            self._apply_exclusion_rules(lead)
            return lead, created

        if lead.organization_id is None and self._include_unassigned_leads:
            lead.organization_id = self.organization_id
        self._fill_if_missing(lead, "category", candidate.category)
        self._fill_if_missing(lead, "address", candidate.address)
        self._fill_if_missing(lead, "neighborhood", candidate.neighborhood)
        self._fill_if_missing(lead, "city", candidate.city)
        self._fill_if_missing(lead, "state", normalized_state)
        self._fill_if_missing(lead, "postal_code", candidate.postal_code)
        self._fill_if_missing(lead, "latitude", candidate.latitude)
        self._fill_if_missing(lead, "longitude", candidate.longitude)
        self._fill_if_missing(lead, "website", candidate.website)
        self._fill_if_missing(lead, "domain", candidate.domain)
        self._fill_if_missing(lead, "email", candidate.email)
        self._fill_if_missing(lead, "phone", candidate.phone)
        self._fill_if_missing(lead, "whatsapp", candidate.whatsapp)
        self._fill_if_missing(lead, "instagram", candidate.instagram)
        self._fill_if_missing(lead, "google_maps_url", candidate.google_maps_url)
        self._fill_if_missing(lead, "google_place_id", candidate.google_place_id)
        self._fill_if_missing(lead, "source_provider", candidate.source_provider)
        self._fill_if_missing(lead, "source_url", candidate.source_url)
        self._apply_exclusion_rules(lead)
        self.db.flush()
        return lead, created

    def add_contact_if_missing(
        self,
        *,
        lead_id: int,
        contact_type: ContactType,
        raw_value: str,
        normalized_value: str | None,
        source_url: str | None,
        source_kind: str,
        source_record_type: str,
        source_record_id: int,
        confidence: float = 0.8,
        is_primary: bool = False,
        label: str | None = None,
        note: str | None = None,
    ) -> LeadContact | None:
        lead = self.get_by_id(lead_id)
        if lead is None:
            raise ValueError(f"Lead {lead_id} not found in organization scope.")

        organization_id = lead.organization_id or self.organization_id
        comparison_value = normalized_value or raw_value
        query = select(LeadContact).where(
            LeadContact.lead_id == lead_id,
            *self._tenant_child_conditions(LeadContact),
            LeadContact.contact_type == contact_type,
            func.coalesce(LeadContact.normalized_value, LeadContact.raw_value) == comparison_value,
            LeadContact.source_record_type == source_record_type,
            LeadContact.source_record_id == source_record_id,
        )
        existing = self.db.execute(query).scalar_one_or_none()
        if existing is not None:
            return None

        contact = LeadContact(
            organization_id=organization_id,
            lead_id=lead_id,
            contact_type=contact_type,
            raw_value=raw_value,
            normalized_value=normalized_value,
            source_url=source_url,
            source_kind=source_kind,
            source_record_type=source_record_type,
            source_record_id=source_record_id,
            confidence=confidence,
            is_primary=is_primary,
            label=label,
            note=note,
        )
        self.db.add(contact)
        self.db.flush()
        return contact

    def sync_canonical_contacts(self, lead: Lead) -> list[str]:
        scoped_lead = self.get_by_id(lead.id)
        if scoped_lead is None:
            raise ValueError(f"Lead {lead.id} not found in organization scope.")

        query = (
            select(LeadContact)
            .where(LeadContact.lead_id == lead.id, *self._tenant_child_conditions(LeadContact))
            .order_by(LeadContact.contact_type.asc(), LeadContact.confidence.desc(), LeadContact.updated_at.desc())
        )
        contacts = self.db.execute(query).scalars().all()
        updated_fields: list[str] = []

        for contact_type, field_name in CONTACT_FIELD_MAP.items():
            typed_contacts = [item for item in contacts if item.contact_type == contact_type]
            if not typed_contacts:
                continue
            best = max(
                typed_contacts,
                key=lambda item: (
                    item.confidence,
                    1 if item.is_primary else 0,
                    item.updated_at.timestamp(),
                    item.id,
                ),
            )
            canonical_value = best.normalized_value or best.raw_value
            if canonical_value and getattr(lead, field_name) != canonical_value:
                setattr(lead, field_name, canonical_value)
                updated_fields.append(field_name)

            for contact in typed_contacts:
                contact.is_primary = contact.id == best.id

        self.db.flush()
        return updated_fields

    def copy_contact_to_lead(
        self,
        source_contact: LeadContact,
        *,
        target_lead_id: int,
        note_suffix: str | None = None,
    ) -> LeadContact | None:
        note = source_contact.note
        if note_suffix:
            note = f"{note or ''} {note_suffix}".strip()
        return self.add_contact_if_missing(
            lead_id=target_lead_id,
            contact_type=source_contact.contact_type,
            raw_value=source_contact.raw_value,
            normalized_value=source_contact.normalized_value,
            source_url=source_contact.source_url,
            source_kind=source_contact.source_kind or "merged_lead",
            source_record_type=source_contact.source_record_type or "lead_contact",
            source_record_id=source_contact.source_record_id or source_contact.id,
            confidence=source_contact.confidence,
            is_primary=False,
            label=source_contact.label,
            note=note,
        )

    def list_raw_records_for_lead(self, lead_id: int) -> list[RawDiscoveryRecord]:
        query = (
            select(RawDiscoveryRecord)
            .join(Lead, RawDiscoveryRecord.lead_id == Lead.id)
            .where(RawDiscoveryRecord.lead_id == lead_id, *self._organization_conditions())
            .order_by(RawDiscoveryRecord.created_at.asc())
        )
        return self.db.execute(query).scalars().all()

    def _build_filter_conditions(self, filters: LeadListFilters) -> list[object]:
        conditions: list[object] = self._organization_conditions()

        if filters.city:
            conditions.append(Lead.city.ilike(filters.city))
        if filters.state:
            conditions.append(Lead.state.ilike(filters.state))
        if filters.status:
            conditions.append(Lead.status == filters.status)
        if filters.category:
            conditions.append(Lead.category.ilike(f"%{filters.category}%"))
        if filters.lead_source_type:
            conditions.append(Lead.lead_source_type == filters.lead_source_type)
        if filters.do_not_contact is not None:
            conditions.append(Lead.do_not_contact == filters.do_not_contact)
        if filters.score_min is not None:
            conditions.append(Lead.lead_score >= filters.score_min)
        if filters.score_max is not None:
            conditions.append(Lead.lead_score <= filters.score_max)
        if filters.has_email is True:
            conditions.append(Lead.email.is_not(None))
            conditions.append(Lead.email != "")
        elif filters.has_email is False:
            conditions.append(or_(Lead.email.is_(None), Lead.email == ""))
        if filters.has_whatsapp is True:
            conditions.append(Lead.whatsapp.is_not(None))
            conditions.append(Lead.whatsapp != "")
        elif filters.has_whatsapp is False:
            conditions.append(or_(Lead.whatsapp.is_(None), Lead.whatsapp == ""))
        if filters.has_instagram is True:
            conditions.append(Lead.instagram.is_not(None))
            conditions.append(Lead.instagram != "")
        elif filters.has_instagram is False:
            conditions.append(or_(Lead.instagram.is_(None), Lead.instagram == ""))
        if filters.sales_region_id is not None:
            conditions.append(Lead.sales_region_id == filters.sales_region_id)
        if filters.market_segment_id is not None:
            conditions.append(Lead.market_segment_id == filters.market_segment_id)
        if filters.market_subsegment_id is not None:
            conditions.append(Lead.market_subsegment_id == filters.market_subsegment_id)
        if filters.assigned_sales_rep_id is not None:
            conditions.append(Lead.assigned_sales_rep_id == filters.assigned_sales_rep_id)
        if filters.has_assignment is True:
            conditions.append(Lead.assigned_sales_rep_id.is_not(None))
        elif filters.has_assignment is False:
            conditions.append(Lead.assigned_sales_rep_id.is_(None))
        if filters.company_size_fit is not None:
            conditions.append(Lead.company_size_fit == filters.company_size_fit.value)
        if filters.trade_type is not None:
            conditions.append(Lead.trade_type == filters.trade_type.value)
        if filters.import_batch_id is not None:
            conditions.append(
                Lead.id.in_(
                    select(RawDiscoveryRecord.lead_id).where(
                        RawDiscoveryRecord.import_batch_id == filters.import_batch_id,
                        RawDiscoveryRecord.lead_id.is_not(None),
                    )
                )
            )
        conditions.extend(self._blocked_conditions(filters.blocked))

        return conditions

    @staticmethod
    def _blocked_conditions(blocked: LeadBlockedFilter) -> list[object]:
        if blocked == "include":
            return []
        if blocked == "only":
            return [Lead.is_blocked.is_(True)]
        return [Lead.is_blocked.is_(False)]

    @staticmethod
    def _sort_expressions(filters: LeadListFilters) -> list[object]:
        sort_column = LEAD_SORT_COLUMNS.get(filters.sort_by, Lead.updated_at)
        if filters.sort_dir == "asc":
            primary_sort = sort_column.asc()
            id_sort = Lead.id.asc()
        else:
            primary_sort = sort_column.desc()
            id_sort = Lead.id.desc()
        if filters.sort_by == "id":
            return [primary_sort]
        return [primary_sort, id_sort]

    def _organization_conditions(self) -> list[object]:
        if self._include_unassigned_leads:
            # Legacy MVP rows can be NULL until the default-organization backfill has run.
            return [or_(Lead.organization_id == self.organization_id, Lead.organization_id.is_(None))]
        return [Lead.organization_id == self.organization_id]

    def _tenant_child_conditions(self, model) -> list[object]:
        if self._include_unassigned_leads:
            # Legacy child rows can be NULL until the child-table backfill has run.
            return [or_(model.organization_id == self.organization_id, model.organization_id.is_(None))]
        return [model.organization_id == self.organization_id]

    def _tenant_child_loader_options(self) -> list[object]:
        return [
            with_loader_criteria(
                LeadContact,
                self._tenant_child_conditions(LeadContact)[0],
                include_aliases=True,
            ),
            with_loader_criteria(
                LeadEnrichmentRecord,
                self._tenant_child_conditions(LeadEnrichmentRecord)[0],
                include_aliases=True,
            ),
            with_loader_criteria(
                ActivityLog,
                self._tenant_child_conditions(ActivityLog)[0],
                include_aliases=True,
            ),
        ]

    @staticmethod
    def _assignment_loader_options() -> list[object]:
        return [
            selectinload(Lead.sales_region),
            selectinload(Lead.market_segment),
            selectinload(Lead.market_subsegment),
            selectinload(Lead.assigned_sales_rep),
            selectinload(Lead.assignment_rule),
        ]

    def _export_loader_options(self) -> list[object]:
        return [
            *self._assignment_loader_options(),
            selectinload(Lead.contacts),
            selectinload(Lead.enrichments),
            selectinload(Lead.raw_discovery_records),
            *self._tenant_child_loader_options(),
        ]

    def _assignment_options(self, model, lead_field) -> list[tuple[int, str]]:
        query = (
            select(model.id, model.name)
            .join(Lead, lead_field == model.id)
            .where(*self._organization_conditions(), *self._blocked_conditions("exclude"))
            .distinct()
            .order_by(model.name.asc(), model.id.asc())
        )
        return [(int(row.id), str(row.name)) for row in self.db.execute(query).all()]

    def _find_existing(self, candidate: DiscoveryLeadCandidate) -> Lead | None:
        organization_conditions = self._organization_conditions()
        if candidate.google_place_id:
            query = select(Lead).where(*organization_conditions, Lead.google_place_id == candidate.google_place_id)
            lead = self.db.execute(query).scalar_one_or_none()
            if lead is not None:
                return lead

        if candidate.domain and candidate.city:
            query = select(Lead).where(
                *organization_conditions,
                Lead.domain == candidate.domain,
                Lead.city == candidate.city,
            )
            lead = self.db.execute(query).scalar_one_or_none()
            if lead is not None:
                return lead

        query = select(Lead).where(
            *organization_conditions,
            Lead.normalized_business_name == candidate.normalized_business_name,
            or_(Lead.city == candidate.city, Lead.city.is_(None)),
        )
        return self.db.execute(query).scalar_one_or_none()

    @staticmethod
    def _fill_if_missing(lead: Lead, field_name: str, new_value: object) -> None:
        if new_value in (None, "", [], {}):
            return
        current_value = getattr(lead, field_name)
        if current_value in (None, "", [], {}):
            setattr(lead, field_name, new_value)

    def _apply_exclusion_rules(self, lead: Lead) -> None:
        from app.services.exclusion_rules import ExclusionRuleService

        ExclusionRuleService(self.db, organization_id=lead.organization_id or self.organization_id).apply_to_lead(lead)
