import pandas as pd

from app.core.constants import CheckStatus
from app.quality.result import RuleResult
from app.quality.rules.base import BaseRule, require_column_list


class RequiredColumnsRule(BaseRule):
    """Fails if any listed column is absent from the file.

    This rule counts columns, not rows: rows_evaluated is the number of
    columns checked, failed_row_count is the number missing.
    """

    rule_type = "required_columns"

    def validate_config(self) -> None:
        require_column_list(self.config)

    def evaluate(self, df: pd.DataFrame) -> RuleResult:
        columns = self.config["columns"]
        missing = [c for c in columns if c not in df.columns]
        details = {"columns": columns, "missing_columns": missing}

        if not missing:
            return self._result(
                CheckStatus.PASS,
                "All required columns are present.",
                rows_evaluated=len(columns),
                details=details,
            )
        return self._result(
            CheckStatus.FAIL,
            f"Missing required column(s): {', '.join(missing)}.",
            rows_evaluated=len(columns),
            failed_row_count=len(missing),
            details=details,
        )