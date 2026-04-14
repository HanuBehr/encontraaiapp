from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class SalesRep(TimestampMixin, Base):
    __tablename__ = "sales_reps"
    __table_args__ = (
        Index("ix_sales_reps_org_active", "organization_id", "is_active"),
        Index("ix_sales_reps_org_external_ref", "organization_id", "external_ref"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32))
    whatsapp: Mapped[str | None] = mapped_column(String(32))
    external_ref: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="sales_reps")
    assignment_rules: Mapped[list["AssignmentRule"]] = relationship("AssignmentRule", back_populates="sales_rep")
    assigned_leads: Mapped[list["Lead"]] = relationship("Lead", back_populates="assigned_sales_rep")
