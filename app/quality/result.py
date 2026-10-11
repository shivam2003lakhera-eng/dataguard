from dataclasses import dataclass, field
from typing import Any

from app.core.constants import CheckStatus, Severity


@dataclass
class RuleResult:
    """The standard answer every quality rule returns."""

    rule_name: str
    rule_type: str
    status: CheckStatus
    severity: Severity
    message: str
    rows_evaluated: int = 0
    failed_row_count: int = 0
    sample_row_indexes: list[int] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: float | None = None