import pandas as pd

from app.core.constants import CheckStatus
from app.quality.result import RuleResult
from app.quality.rules.base import BaseRule

MAX_SAMPLES = 5


class RequiredValuesRule(BaseRule):
    """Fails if any listed column has missing or blank values."""

    rule_type = "required_values"

    def evaluate(self, df: pd.DataFrame) -> RuleResult:
        columns = self.config.get("columns")
        if not isinstance(columns, list) or not columns:
            return self._error("Config needs a non-empty 'columns' list.")

        absent = [col for col in columns if col not in df.columns]
        if absent:
            return self._error(f"Columns not found in data: {absent}")

        missing_rows = pd.Series(False, index=df.index)
        for col in columns:
            blank = df[col].isna() | (df[col].astype(str).str.strip() == "")
            missing_rows = missing_rows | blank

        failed = int(missing_rows.sum())
        if failed == 0:
            return self._result(
                CheckStatus.PASS,
                "No missing values in required columns.",
                rows_evaluated=len(df),
                details={"columns": columns},
            )

        samples = [int(i) for i in df.index[missing_rows][:MAX_SAMPLES]]
        return self._result(
            CheckStatus.FAIL,
            f"{failed} row(s) have missing values in required columns.",
            rows_evaluated=len(df),
            failed_row_count=failed,
            sample_row_indexes=samples,
            details={"columns": columns},
        )