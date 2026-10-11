from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Dataset(Base):
    """One uploaded CSV. Only metadata is stored, never the rows."""

    __tablename__ = "datasets"
    __table_args__ = (
        CheckConstraint("row_count >= 0", name="ck_datasets_row_count"),
        CheckConstraint("column_count >= 0", name="ck_datasets_column_count"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    original_filename: Mapped[str] = mapped_column(String(255))
    row_count: Mapped[int] = mapped_column(Integer)
    column_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profiles: Mapped[list["DatasetProfile"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan", passive_deletes=True
    )
    rules: Mapped[list["QualityRule"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan", passive_deletes=True
    )
    runs: Mapped[list["QualityRun"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan", passive_deletes=True
    )