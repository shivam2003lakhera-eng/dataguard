import pandas as pd

from app.core.constants import CheckStatus
from app.core.exceptions import ConfigurationError
from app.quality.result import RuleResult
from app.quality.rules.base import (
    MAX_SAMPLES,
    BaseRule,
    is_finite_number,
    require_column_name,
)


class NumericRangeRule(BaseRule):
    """Fails if numeric values fall outside the configured min/max.

    Text that is not a finite number is skipped here; the data_type rule
    is the one that reports it.
    """

    rule_type = "numeric_range"

    def validate_config(self) -> None:
        require_column_name(self.config)
        low = self.config.get("min")
        high = self.config.get("max")
        if low is None and high is None:
            raise ConfigurationError("Config needs at least one of 'min' or 'max'.")
        for label, value in (("min", low), ("max", high)):
            if value is not None and not is_finite_number(value):
                raise ConfigurationError(f"'{label}' must be a finite number.", {"field": label})
        if low is not None and high is not None and low > high:
            raise ConfigurationError("'min' cannot be greater than 'max'.")

    def evaluate(self, df: pd.DataFrame) -> RuleResult:
        column = self.config["column"]
        low = self.config.get("min")
        high = self.config.get("max")

        problem = self._absent_columns_failure(df, [column])
        if problem:
            return problem

        numbers = pd.to_numeric(df[column], errors="coerce")
        numbers = numbers.where(numbers.abs() != float("inf"))  # inf is not a usable number

        outside = pd.Series(False, index=df.index)
        if low is not None:
            outside = outside | (numbers < low)
        if high is not None:
            outside = outside | (numbers > high)

        checked = int(numbers.notna().sum())
        failed = int(outside.sum())
        details = {"column": column, "min": low, "max": high}

        if failed == 0:
            return self._result(
                CheckStatus.PASS,
                f"All numeric values in '{column}' are within range.",
                rows_evaluated=checked,
                details=details,
            )
        return self._result(
            CheckStatus.FAIL,
            f"{failed} value(s) in '{column}' are outside the allowed range.",
            rows_evaluated=checked,
            failed_row_count=failed,
            sample_row_indexes=[int(i) for i in df.index[outside][:MAX_SAMPLES]],
            details=details,
        )