import pandas as pd

from app.core.constants import CheckStatus
from app.quality.result import RuleResult
from app.quality.rules.base import BaseRule

MAX_SAMPLES = 5


class AllowedValuesRule(BaseRule):
    """Fails if a column contains values outside the configured list."""

    rule_type = "allowed_values"

    def evaluate(self, df: pd.DataFrame) -> RuleResult:
        column = self.config.get("column")
        allowed = self.config.get("allowed")
        case_sensitive = self.config.get("case_sensitive", True)

        if not isinstance(column, str):
            return self._error("Config needs a 'column' name.")
        if column not in df.columns:
            return self._error(f"Column not found in data: {column}")
        if not isinstance(allowed, list) or not allowed:
            return self._error("Config needs a non-empty 'allowed' list.")

        allowed_set = {str(v).strip() for v in allowed}
        if not case_sensitive:
            allowed_set = {v.upper() for v in allowed_set}

        present = df[column].notna()
        values = df.loc[present, column].astype(str).str.strip()
        if not case_sensitive:
            values = values.str.upper()

        bad = ~values.isin(allowed_set)
        failed = int(bad.sum())
        details = {
            "column": column,
            "allowed": allowed,
            "case_sensitive": case_sensitive,
        }

        if failed == 0:
            return self._result(
                CheckStatus.PASS,
                f"All values in '{column}' are allowed.",
                rows_evaluated=int(present.sum()),
                details=details,
            )

        bad_index = values.index[bad]
        details["bad_values"] = sorted(set(values[bad]))[:MAX_SAMPLES]
        return self._result(
            CheckStatus.FAIL,
            f"{failed} value(s) in '{column}' are not in the allowed list.",
            rows_evaluated=int(present.sum()),
            failed_row_count=failed,
            sample_row_indexes=[int(i) for i in bad_index[:MAX_SAMPLES]],
            details=details,
        )