from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import RunStatus
from app.db.base import Base, in_values


class QualityRun(Base):
    __tablename__ = "quality_runs"
    __table_args__ = (
        CheckConstraint(in_values("status", RunStatus), name="ck_quality_runs_status"),
        CheckConstraint("checks_passed >= 0", name="ck_quality_runs_passed"),
        CheckConstraint("checks_failed >= 0", name="ck_quality_runs_failed"),
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

    dataset: Mapped["Dataset"] = relationship(back_populates="runs")
    results: Mapped[list["QualityResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )