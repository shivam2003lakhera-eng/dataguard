from abc import ABC, abstractmethod
from typing import Any

import pandas as pd

from app.core.constants import CheckStatus, Severity
from app.quality.result import RuleResult


class BaseRule(ABC):
    """Template that every quality rule must follow."""

    rule_type: str = "base"

    def __init__(
        self,
        name: str,
        config: dict[str, Any],
        severity: Severity = Severity.WARNING,
    ) -> None:
        self.name = name
        self.config = config
        self.severity = severity

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
        """Build a RuleResult with this rule's name, type, and severity filled in."""
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

    def _error(self, message: str) -> RuleResult:
        """Build an ERROR result: the check itself could not run."""
        return self._result(CheckStatus.ERROR, message)