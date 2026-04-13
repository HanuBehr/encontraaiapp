from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.enums import ContactType
from app.models.lead import Lead
from app.models.lead_contact import LeadContact
from app.models.raw_discovery_record import RawDiscoveryRecord
from app.schemas.discovery import DiscoveryLeadCandidate
from app.schemas.lead import LeadListFilters


CONTACT_FIELD_MAP: dict[ContactType, str] = {
    ContactType.EMAIL: "email",
    ContactType.PHONE: "phone",
    ContactType.WHATSAPP: "whatsapp",
    ContactType.INSTAGRAM: "instagram",
}


class LeadRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_leads(self, filters: LeadListFilters) -> tuple[list[Lead], int]:
        conditions = self._build_filter_conditions(filters)
        total = self.db.execute(select(func.count(Lead.id)).where(*conditions)).scalar_one()
        query = (
            select(Lead)
            .where(*conditions)
            .order_by(Lead.updated_at.desc(), Lead.id.desc())
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
            .options(
                selectinload(Lead.contacts),
                selectinload(Lead.enrichments),
                selectinload(Lead.raw_discovery_records),
            )
            .where(*conditions)
            .order_by(Lead.id.asc())
        )
        return self.db.execute(query).scalars().all()

    def get_by_id(self, lead_id: int) -> Lead | None:
        return self.db.get(Lead, lead_id)

    def get_detail(self, lead_id: int) -> Lead | None:
        query = (
            select(Lead)
            .options(
                selectinload(Lead.contacts),
                selectinload(Lead.enrichments),
                selectinload(Lead.activity_logs),
                selectinload(Lead.raw_discovery_records),
                selectinload(Lead.outreach_drafts),
            )
            .where(Lead.id == lead_id)
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
                selectinload(Lead.contacts),
                selectinload(Lead.enrichments),
                selectinload(Lead.raw_discovery_records),
                selectinload(Lead.outreach_drafts),
                selectinload(Lead.activity_logs),
            )
            .where(Lead.id == lead_id)
        )
        return self.db.execute(query).scalar_one_or_none()

    def get_by_ids(self, lead_ids: Iterable[int]) -> list[Lead]:
        normalized_ids = list(dict.fromkeys(lead_ids))
        if not normalized_ids:
            return []
        query = (
            select(Lead)
            .options(
                selectinload(Lead.contacts),
                selectinload(Lead.enrichments),
                selectinload(Lead.raw_discovery_records),
            )
            .where(Lead.id.in_(normalized_ids))
            .order_by(Lead.id.asc())
        )
        return self.db.execute(query).scalars().all()

    def list_distinct_cities(self) -> list[str]:
        query = select(Lead.city).where(Lead.city.is_not(None)).distinct().order_by(Lead.city.asc())
        return [value for value in self.db.execute(query).scalars().all() if value]

    def list_distinct_categories(self) -> list[str]:
        query = select(Lead.category).where(Lead.category.is_not(None)).distinct().order_by(Lead.category.asc())
        return [value for value in self.db.execute(query).scalars().all() if value]

    def get_overview_snapshot(self, recent_limit: int = 10) -> tuple[dict[str, int], list[Lead]]:
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
        )
        metrics_row = self.db.execute(metrics_query).one()
        recent_query = (
            select(Lead)
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

        if lead is None:
            lead = Lead(
                business_name=candidate.business_name,
                normalized_business_name=candidate.normalized_business_name,
                category=candidate.category,
                address=candidate.address,
                neighborhood=candidate.neighborhood,
                city=candidate.city,
                state=candidate.state,
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
            )
            self.db.add(lead)
            self.db.flush()
            return lead, created

        self._fill_if_missing(lead, "category", candidate.category)
        self._fill_if_missing(lead, "address", candidate.address)
        self._fill_if_missing(lead, "neighborhood", candidate.neighborhood)
        self._fill_if_missing(lead, "city", candidate.city)
        self._fill_if_missing(lead, "state", candidate.state)
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
        comparison_value = normalized_value or raw_value
        query = select(LeadContact).where(
            LeadContact.lead_id == lead_id,
            LeadContact.contact_type == contact_type,
            func.coalesce(LeadContact.normalized_value, LeadContact.raw_value) == comparison_value,
            LeadContact.source_record_type == source_record_type,
            LeadContact.source_record_id == source_record_id,
        )
        existing = self.db.execute(query).scalar_one_or_none()
        if existing is not None:
            return None

        contact = LeadContact(
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
        query = (
            select(LeadContact)
            .where(LeadContact.lead_id == lead.id)
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
            .where(RawDiscoveryRecord.lead_id == lead_id)
            .order_by(RawDiscoveryRecord.created_at.asc())
        )
        return self.db.execute(query).scalars().all()

    def _build_filter_conditions(self, filters: LeadListFilters) -> list[object]:
        conditions: list[object] = []

        if filters.city:
            conditions.append(Lead.city.ilike(filters.city))
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

        return conditions

    def _find_existing(self, candidate: DiscoveryLeadCandidate) -> Lead | None:
        if candidate.google_place_id:
            query = select(Lead).where(Lead.google_place_id == candidate.google_place_id)
            lead = self.db.execute(query).scalar_one_or_none()
            if lead is not None:
                return lead

        if candidate.domain and candidate.city:
            query = select(Lead).where(Lead.domain == candidate.domain, Lead.city == candidate.city)
            lead = self.db.execute(query).scalar_one_or_none()
            if lead is not None:
                return lead

        query = select(Lead).where(
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
