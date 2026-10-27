import pandas as pd

from app.core.constants import CheckStatus
from app.core.missing import is_missing
from app.quality.result import RuleResult
from app.quality.rules.base import MAX_SAMPLES, BaseRule, require_column_list


class RequiredValuesRule(BaseRule):
    """Fails if any listed column has missing or blank values."""

    rule_type = "required_values"

    def validate_config(self) -> None:
        require_column_list(self.config)

    def evaluate(self, df: pd.DataFrame) -> RuleResult:
        columns = self.config["columns"]
        problem = self._absent_columns_failure(df, columns)
        if problem:
            return problem

        missing_rows = pd.Series(False, index=df.index)
        for col in columns:
            missing_rows = missing_rows | is_missing(df[col])

        failed = int(missing_rows.sum())
        details = {"columns": columns}
        if failed == 0:
            return self._result(
                CheckStatus.PASS,
                "No missing values in required columns.",
                rows_evaluated=len(df),
                details=details,
            )
        return self._result(
            CheckStatus.FAIL,
            f"{failed} row(s) have missing values in required columns.",
            rows_evaluated=len(df),
            failed_row_count=failed,
            sample_row_indexes=[int(i) for i in df.index[missing_rows][:MAX_SAMPLES]],
            details=details,
        )