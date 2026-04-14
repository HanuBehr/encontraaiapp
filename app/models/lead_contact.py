from __future__ import annotations

from sqlalchemy import Enum as SAEnum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import ContactType
from app.models.base import Base, TimestampMixin


class LeadContact(TimestampMixin, Base):
    __tablename__ = "lead_contacts"
    __table_args__ = (
        Index("ix_lead_contacts_type_value", "contact_type", "normalized_value"),
        Index("ix_lead_contacts_lead_primary", "lead_id", "is_primary"),
        Index("ix_lead_contacts_org_type_value", "organization_id", "contact_type", "normalized_value"),
        Index("ix_lead_contacts_org_lead_primary", "organization_id", "lead_id", "is_primary"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), nullable=False, index=True)
    contact_type: Mapped[ContactType] = mapped_column(
        SAEnum(ContactType, native_enum=False),
        nullable=False,
        index=True,
    )
    raw_value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str | None] = mapped_column(String(255))
    label: Mapped[str | None] = mapped_column(String(100))
    source_url: Mapped[str | None] = mapped_column(String(500))
    source_kind: Mapped[str | None] = mapped_column(String(100))
    source_record_type: Mapped[str | None] = mapped_column(String(100))
    source_record_id: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_primary: Mapped[bool] = mapped_column(default=False, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)

    organization: Mapped["Organization | None"] = relationship("Organization", back_populates="lead_contacts")
    lead: Mapped["Lead"] = relationship("Lead", back_populates="contacts")
