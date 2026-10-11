import pandas as pd

from app.core.constants import CheckStatus
from app.core.exceptions import ConfigurationError
from app.profiling.statistics import parse_iso_dates, to_finite_numbers
from app.quality.result import RuleResult
from app.quality.rules.base import MAX_SAMPLES, BaseRule, require_column_name

SUPPORTED_TYPES = ("integer", "float", "date")
INTEGER_PATTERN = r"^[+-]?\d+$"


class DataTypeRule(BaseRule):
    """Fails if non-missing values cannot be converted to the configured type."""

    rule_type = "data_type"

    def validate_config(self) -> None:
        require_column_name(self.config)
        if self.config.get("data_type") not in SUPPORTED_TYPES:
            raise ConfigurationError(
                f"'data_type' must be one of: {', '.join(SUPPORTED_TYPES)}.",
                {"field": "data_type"},
            )

    def evaluate(self, df: pd.DataFrame) -> RuleResult:
        column = self.config["column"]
        data_type = self.config["data_type"]

        problem = self._absent_columns_failure(df, [column])
        if problem:
            return problem

        values = df[column].dropna()
        values = values[values.astype(str).str.strip() != ""]  # blanks are "missing", not wrong

        if data_type == "integer":
            ok = values.astype(str).str.strip().str.match(INTEGER_PATTERN)
        elif data_type == "float":
            ok = to_finite_numbers(values).notna()
        else:
            ok = parse_iso_dates(values).notna()

        bad = ~ok
        failed = int(bad.sum())
        details = {"column": column, "data_type": data_type}

        if failed == 0:
            return self._result(
                CheckStatus.PASS,
                f"All values in '{column}' are valid {data_type} values.",
                rows_evaluated=len(values),
                details=details,
            )
        details["bad_values"] = [str(v) for v in values[bad].unique()[:MAX_SAMPLES]]
        return self._result(
            CheckStatus.FAIL,
            f"{failed} value(s) in '{column}' are not valid {data_type} values.",
            rows_evaluated=len(values),
            failed_row_count=failed,
            sample_row_indexes=[int(i) for i in values.index[bad][:MAX_SAMPLES]],
            details=details,
        )