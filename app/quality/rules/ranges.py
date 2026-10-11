import pandas as pd

from app.core.constants import CheckStatus
from app.quality.result import RuleResult
from app.quality.rules.base import BaseRule

MAX_SAMPLES = 5


class NumericRangeRule(BaseRule):
    """Fails if numeric values fall outside the configured min/max."""

    rule_type = "numeric_range"

    def evaluate(self, df: pd.DataFrame) -> RuleResult:
        column = self.config.get("column")
        low = self.config.get("min")
        high = self.config.get("max")

        if not isinstance(column, str):
            return self._error("Config needs a 'column' name.")
        if column not in df.columns:
            return self._error(f"Column not found in data: {column}")
        if low is None and high is None:
            return self._error("Config needs at least one of 'min' or 'max'.")
        for limit in (low, high):
            if limit is not None and not isinstance(limit, (int, float)):
                return self._error("'min' and 'max' must be numbers.")
        if low is not None and high is not None and low > high:
            return self._error("'min' cannot be greater than 'max'.")

        numbers = pd.to_numeric(df[column], errors="coerce")
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

        samples = [int(i) for i in df.index[outside][:MAX_SAMPLES]]
        return self._result(
            CheckStatus.FAIL,
            f"{failed} value(s) in '{column}' are outside the allowed range.",
            rows_evaluated=checked,
            failed_row_count=failed,
            sample_row_indexes=samples,
            details=details,
        )