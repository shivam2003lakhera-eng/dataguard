from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import CheckStatus, Severity
from app.db.base import Base, in_values


class QualityResult(Base):
    __tablename__ = "quality_results"
    __table_args__ = (
        CheckConstraint(in_values("status", CheckStatus), name="ck_quality_results_status"),
        CheckConstraint(in_values("severity", Severity), name="ck_quality_results_severity"),
        CheckConstraint("rows_evaluated >= 0", name="ck_quality_results_evaluated"),
        CheckConstraint("rows_failed >= 0", name="ck_quality_results_failed"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("quality_runs.id", ondelete="CASCADE"), index=True
    )
    # Nullable: if a rule is deleted later, its historical results are kept.
    rule_id: Mapped[int | None] = mapped_column(
        ForeignKey("quality_rules.id", ondelete="SET NULL"), index=True
    )
    rule_name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(10))
    severity: Mapped[str] = mapped_column(String(10))
    rows_evaluated: Mapped[int] = mapped_column(Integer)
    rows_failed: Mapped[int] = mapped_column(Integer)
    message: Mapped[str] = mapped_column(Text)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped["QualityRun"] = relationship(back_populates="results")