from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum as SAEnum, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import ImportBatchStatus, ImportBatchType
from app.models.base import Base, TimestampMixin


class ImportBatch(TimestampMixin, Base):
    __tablename__ = "import_batches"
    __table_args__ = (Index("ix_import_batches_type_status", "batch_type", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_type: Mapped[ImportBatchType] = mapped_column(
        SAEnum(ImportBatchType, native_enum=False),
        nullable=False,
        index=True,
    )
    status: Mapped[ImportBatchStatus] = mapped_column(
        SAEnum(ImportBatchStatus, native_enum=False),
        nullable=False,
        default=ImportBatchStatus.PENDING,
        index=True,
    )
    source_provider: Mapped[str | None] = mapped_column(String(100))
    source_query: Mapped[str | None] = mapped_column(String(255))
    location_label: Mapped[str | None] = mapped_column(String(255))
    input_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    raw_discovery_records: Mapped[list["RawDiscoveryRecord"]] = relationship(
        "RawDiscoveryRecord",
        back_populates="import_batch",
    )
