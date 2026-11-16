import math
from abc import ABC, abstractmethod
from typing import Any

import pandas as pd

from app.core.constants import CheckStatus, Severity
from app.core.exceptions import ConfigurationError
from app.quality.result import QUALITY, SCHEMA, RuleResult

MAX_SAMPLES = 5


def require_column_name(config: dict[str, Any], key: str = "column") -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(
            f"Config needs a non-empty '{key}' text value.", {"field": key}
        )
    return value


def require_column_list(config: dict[str, Any], key: str = "columns") -> list[str]:
    value = config.get(key)
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(v, str) and v.strip() for v in value)
    ):
        raise ConfigurationError(
            f"Config needs a non-empty '{key}' list of column names.", {"field": key}
        )
    return value


def is_finite_number(value: Any) -> bool:
    """True for int/float, but not bool, NaN or infinity."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


class BaseRule(ABC):
    """Template that every quality rule must follow."""

    rule_type: str = "base"
    # "schema" rules judge the shape of the file. "quality" rules judge the rows.
    category: str = QUALITY
    # Short per-row explanation used when a row is rejected by this rule.
    row_reason: str = ""

    def __init__(
        self,
        name: str,
        config: dict[str, Any],
        severity: Severity = Severity.MEDIUM,
    ) -> None:
        self.name = name
        self.config = config
        self.severity = severity
        self.validate_config()

    def validate_config(self) -> None:
        """Raise ConfigurationError if the config is invalid. Default: accept."""

    @abstractmethod
    def evaluate(self, df: pd.DataFrame) -> RuleResult:
        """Check the data and return a RuleResult."""

    def _rule_columns(self) -> list[str]:
        """The column names this rule is configured for (for reports)."""
        columns = self.config.get("columns")
        if isinstance(columns, list):
            return [str(c) for c in columns]
        column = self.config.get("column")
        return [column] if isinstance(column, str) else []

    def _result(
        self,
        status: CheckStatus,
        message: str,
        rows_evaluated: int = 0,
        failed_row_count: int = 0,
        sample_row_indexes: list[int] | None = None,
        details: dict[str, Any] | None = None,
        rejected_index: list[int] | None = None,
        reason: str | None = None,
        category: str | None = None,
        columns: list[str] | None = None,
    ) -> RuleResult:
        return RuleResult(
            rule_name=self.name,
            rule_type=self.rule_type,
            status=status,
            severity=self.severity,
            message=message,
            rows_evaluated=rows_evaluated,
            failed_row_count=failed_row_count,
            sample_row_indexes=sample_row_indexes or [],
            details=details or {},
            category=category or self.category,
            columns=self._rule_columns() if columns is None else columns,
            reason=self.row_reason if reason is None else reason,
            rejected_index=rejected_index or [],
        )

    def _config_failure(self, message: str, columns: list[str] | None = None) -> RuleResult:
        """A visible FAIL for a problem found only at run time (never skipped).

        It is a schema failure: the rule could not look at the data at all.
        """
        return self._result(
            CheckStatus.FAIL,
            f"Configuration error: {message}",
            details={"error": "configuration"},
            category=SCHEMA,
            columns=columns,
        )

    def _absent_columns_failure(
        self, df: pd.DataFrame, columns: list[str]
    ) -> RuleResult | None:
        """Return a failure result if any column is missing from the data."""
        absent = [c for c in columns if c not in df.columns]
        if absent:
            return self._config_failure(
                f"Column not found in data: {', '.join(absent)}", columns=absent
            )
        return None
