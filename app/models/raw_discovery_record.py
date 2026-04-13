from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, utcnow


class RawDiscoveryRecord(CreatedAtMixin, Base):
    __tablename__ = "raw_discovery_records"
    __table_args__ = (
        Index("ix_raw_discovery_provider_record", "provider", "provider_record_id"),
        Index("ix_raw_discovery_batch_created", "import_batch_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), nullable=False, index=True)
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("leads.id"), index=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_record_id: Mapped[str | None] = mapped_column(String(128))
    search_term: Mapped[str | None] = mapped_column(String(255))
    search_input: Mapped[str | None] = mapped_column(String(255))
    center_lat: Mapped[float | None] = mapped_column(Float)
    center_lng: Mapped[float | None] = mapped_column(Float)
    radius_m: Mapped[int | None] = mapped_column(Integer)
    source_url: Mapped[str | None] = mapped_column(String(500))
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    import_batch: Mapped["ImportBatch"] = relationship("ImportBatch", back_populates="raw_discovery_records")
    lead: Mapped["Lead | None"] = relationship("Lead", back_populates="raw_discovery_records")
