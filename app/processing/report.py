from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RuleSummary:
    """One rule's outcome, as shown in the report."""

    name: str
    rule_type: str
    category: str          # "schema" or "quality"
    severity: str
    status: str            # PASS or FAIL
    rows_evaluated: int
    rows_failed: int       # the rule's own count (for duplicates: every row with a twin)
    rows_rejected: int     # rows this rule rejects (for duplicates: extra copies only)
    columns: list[str]
    message: str


@dataclass
class RejectedRow:
    """Why one row was rejected by one rule. Never contains cell values."""

    row_index: int         # 0-based position in the data (the first data row is 0)
    data_row: int          # 1-based (the first data row is 1)
    rule: str
    rule_type: str
    columns: list[str]
    reason: str


@dataclass
class PipelineReport:
    """The structured result of one pipeline run.

    Every number comes from real execution. A number that could not be measured
    (for example the row count when the file could not be read) is None, never 0.

    Counting rules:
      * A row is REJECTED if at least one quality rule rejects it. A row that
        fails several rules is counted once.
      * valid_rows + rejected_rows == source_rows.
      * overlap_rows = (sum of every rule's rejected rows) - rejected_rows.
      * Schema rules (and rules that could not run) judge the file, not rows, so
        they never reject rows. They set loadable to False instead.
    """

    run_id: str
    status: str                       # SUCCESS, COMPLETED_WITH_ISSUES or FAILED
    source_file: str | None = None
    source_rows: int | None = None
    source_columns: int | None = None
    valid_rows: int | None = None
    rejected_rows: int | None = None
    duplicate_rows: int | None = None  # extra copies of whole rows, from the profile
    overlap_rows: int | None = None
    rules_executed: int = 0
    rules_passed: int = 0
    rules_failed: int = 0
    schema_failures: int = 0
    quality_failures: int = 0
    rules_crashed: int = 0
    loadable: bool | None = None       # True only if no schema failure occurred
    duration_ms: float | None = None
    timings_ms: dict[str, float] = field(default_factory=dict)
    rules: list[RuleSummary] = field(default_factory=list)
    rejected_sample: list[RejectedRow] = field(default_factory=list)
    rejected_sample_truncated: bool = False
    profile: dict[str, Any] | None = None
    error: dict[str, str] | None = None  # {"code": ..., "message": ...} when FAILED

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
