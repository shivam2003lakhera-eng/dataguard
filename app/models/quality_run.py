from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import RunStatus
from app.db.base import Base, in_values


class QualityRun(Base):
    __tablename__ = "quality_runs"
    __table_args__ = (
        CheckConstraint(in_values("status", RunStatus), name="ck_quality_runs_status"),
        CheckConstraint("checks_passed >= 0", name="ck_quality_runs_passed"),
        CheckConstraint("checks_failed >= 0", name="ck_quality_runs_failed"),
        CheckConstraint("source_rows >= 0", name="ck_quality_runs_source_rows"),
        CheckConstraint("duration_ms >= 0", name="ck_quality_runs_duration"),
        # The database itself guarantees valid + rejected = source whenever they are recorded.
        CheckConstraint(
            "source_rows IS NULL OR (valid_rows >= 0 AND rejected_rows >= 0 "
            "AND valid_rows + rejected_rows = source_rows)",
            name="ck_quality_runs_row_accounting",
        ),
        # Every valid row is inserted, updated, unchanged or skipped: nothing goes missing.
        CheckConstraint(
            "rows_inserted IS NULL OR (rows_inserted >= 0 AND rows_updated >= 0 "
            "AND rows_unchanged >= 0 AND rows_skipped >= 0 "
            "AND rows_inserted + rows_updated + rows_unchanged + rows_skipped = valid_rows)",
            name="ck_quality_runs_load_accounting",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(30))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checks_passed: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    checks_failed: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error_message: Mapped[str | None] = mapped_column(Text)

    # Execution metrics. NULL means "not measured" (older runs, or a run that failed).
    source_rows: Mapped[int | None] = mapped_column(Integer)
    valid_rows: Mapped[int | None] = mapped_column(Integer)
    rejected_rows: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    loadable: Mapped[bool | None] = mapped_column(Boolean)  # no schema check failed
    file_sha256: Mapped[str | None] = mapped_column(String(64))  # identifies the uploaded file
    # Loading (only for datasets with key_columns). NULL means nothing was loaded.
    rows_inserted: Mapped[int | None] = mapped_column(Integer)
    rows_updated: Mapped[int | None] = mapped_column(Integer)
    rows_unchanged: Mapped[int | None] = mapped_column(Integer)
    rows_skipped: Mapped[int | None] = mapped_column(Integer)

    dataset: Mapped["Dataset"] = relationship(back_populates="runs")
    results: Mapped[list["QualityResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )
