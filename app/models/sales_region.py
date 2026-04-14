from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class SalesRegion(TimestampMixin, Base):
    __tablename__ = "sales_regions"
    __table_args__ = (
        Index("ix_sales_regions_org_type", "organization_id", "region_type"),
        Index("ix_sales_regions_org_code", "organization_id", "code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    region_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    state: Mapped[str | None] = mapped_column(String(80))
    code: Mapped[str | None] = mapped_column(String(80))
    cities_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    postal_codes_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="sales_regions")
    assignment_rules: Mapped[list["AssignmentRule"]] = relationship("AssignmentRule", back_populates="sales_region")
    assigned_leads: Mapped[list["Lead"]] = relationship("Lead", back_populates="sales_region")
