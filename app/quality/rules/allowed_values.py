import pandas as pd

from app.core.constants import CheckStatus
from app.core.exceptions import ConfigurationError
from app.quality.result import RuleResult
from app.quality.rules.base import MAX_SAMPLES, BaseRule, require_column_name


class AllowedValuesRule(BaseRule):
    """Fails if a column contains values outside the configured list."""

    rule_type = "allowed_values"

    def validate_config(self) -> None:
        require_column_name(self.config)
        allowed = self.config.get("allowed")
        if not isinstance(allowed, list) or not allowed:
            raise ConfigurationError("Config needs a non-empty 'allowed' list.", {"field": "allowed"})
        if not isinstance(self.config.get("case_sensitive", True), bool):
            raise ConfigurationError("'case_sensitive' must be true or false.", {"field": "case_sensitive"})

    def evaluate(self, df: pd.DataFrame) -> RuleResult:
        column = self.config["column"]
        allowed = self.config["allowed"]
        case_sensitive = self.config.get("case_sensitive", True)

        problem = self._absent_columns_failure(df, [column])
        if problem:
            return problem

        allowed_set = {str(v).strip() for v in allowed}
        if not case_sensitive:
            allowed_set = {v.upper() for v in allowed_set}

        present = df[column].notna()
        values = df.loc[present, column].astype(str).str.strip()
        if not case_sensitive:
            values = values.str.upper()

        bad = ~values.isin(allowed_set)
        failed = int(bad.sum())
        details = {"column": column, "allowed": allowed, "case_sensitive": case_sensitive}

        if failed == 0:
            return self._result(
                CheckStatus.PASS,
                f"All values in '{column}' are allowed.",
                rows_evaluated=int(present.sum()),
                details=details,
            )
        details["bad_values"] = sorted(set(values[bad]))[:MAX_SAMPLES]
        return self._result(
            CheckStatus.FAIL,
            f"{failed} value(s) in '{column}' are not in the allowed list.",
            rows_evaluated=int(present.sum()),
            failed_row_count=failed,
            sample_row_indexes=[int(i) for i in values.index[bad][:MAX_SAMPLES]],
            details=details,
        )