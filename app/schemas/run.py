from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_id: int | None
    rule_name: str
    status: str
    severity: str
    rows_evaluated: int
    rows_failed: int
    message: str
    details: dict[str, Any] | None
    created_at: datetime


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dataset_id: int
    status: str
    started_at: datetime
    completed_at: datetime | None
    checks_passed: int
    checks_failed: int
    error_message: str | None

class RunListItem(RunOut):
    dataset_name: str


class RunDetail(RunOut):
    results: list[ResultOut]


def run_to_detail(run) -> RunDetail:
    """Build the full report while the database session is still open."""
    return RunDetail(
        **RunOut.model_validate(run).model_dump(),
        results=[ResultOut.model_validate(r) for r in sorted(run.results, key=lambda r: r.id)],
    )