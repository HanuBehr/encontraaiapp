from __future__ import annotations

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class MarketSegment(TimestampMixin, Base):
    __tablename__ = "market_segments"
    __table_args__ = (
        Index("ix_market_segments_org_key", "organization_id", "key"),
        Index("ix_market_segments_org_active", "organization_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="market_segments")
    subsegments: Mapped[list["MarketSubsegment"]] = relationship("MarketSubsegment", back_populates="segment")
    assignment_rules: Mapped[list["AssignmentRule"]] = relationship("AssignmentRule", back_populates="market_segment")
    classified_leads: Mapped[list["Lead"]] = relationship("Lead", back_populates="market_segment")


class MarketSubsegment(TimestampMixin, Base):
    __tablename__ = "market_subsegments"
    __table_args__ = (
        Index("ix_market_subsegments_org_key", "organization_id", "key"),
        Index("ix_market_subsegments_segment_active", "segment_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    segment_id: Mapped[int] = mapped_column(ForeignKey("market_segments.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    keywords_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    organization: Mapped["Organization"] = relationship("Organization")
    segment: Mapped["MarketSegment"] = relationship("MarketSegment", back_populates="subsegments")
    assignment_rules: Mapped[list["AssignmentRule"]] = relationship("AssignmentRule", back_populates="market_subsegment")
    classified_leads: Mapped[list["Lead"]] = relationship("Lead", back_populates="market_subsegment")
