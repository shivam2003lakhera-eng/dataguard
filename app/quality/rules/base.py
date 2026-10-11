import math
from abc import ABC, abstractmethod
from typing import Any

import pandas as pd

from app.core.constants import CheckStatus, Severity
from app.core.exceptions import ConfigurationError
from app.quality.result import RuleResult

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

    def _result(
        self,
        status: CheckStatus,
        message: str,
        rows_evaluated: int = 0,
        failed_row_count: int = 0,
        sample_row_indexes: list[int] | None = None,
        details: dict[str, Any] | None = None,
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
        )

    def _config_failure(self, message: str) -> RuleResult:
        """A visible FAIL for a problem found only at run time (never skipped)."""
        return self._result(
            CheckStatus.FAIL,
            f"Configuration error: {message}",
            details={"error": "configuration"},
        )

    def _absent_columns_failure(
        self, df: pd.DataFrame, columns: list[str]
    ) -> RuleResult | None:
        """Return a failure result if any column is missing from the data."""
        absent = [c for c in columns if c not in df.columns]
        if absent:
            return self._config_failure(f"Column not found in data: {', '.join(absent)}")
        return None