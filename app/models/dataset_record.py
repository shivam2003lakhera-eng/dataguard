from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DatasetRecord(Base):
    """One loaded row of a dataset. Only exists if the dataset opted in with key_columns.

    row_key identifies the record (the key column values as JSON text). Loading the
    same key again updates this row instead of adding a copy, so loads are idempotent.
    """

    __tablename__ = "dataset_records"
    __table_args__ = (
        UniqueConstraint("dataset_id", "row_key", name="uq_dataset_records_key"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    row_key: Mapped[str] = mapped_column(String(500))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    dataset: Mapped["Dataset"] = relationship(back_populates="records")
