from dataclasses import dataclass, field
from typing import Any

from app.core.constants import CheckStatus, Severity

SCHEMA = "schema"    # judges the shape of the file: columns, headers, configuration
QUALITY = "quality"  # judges the values inside the rows


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
    # Added for row-level accounting. These are kept in memory for the pipeline
    # report; the database layer does not store them.
    category: str = QUALITY
    columns: list[str] = field(default_factory=list)  # columns the rule looked at
    reason: str = ""                                    # short per-row explanation
    rejected_index: list[int] = field(default_factory=list)  # rows this rule rejects
