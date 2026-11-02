import pandas as pd

from app.core.constants import CheckStatus
from app.core.exceptions import ConfigurationError
from app.quality.result import SCHEMA, RuleResult
from app.quality.rules.base import BaseRule, require_column_list


class RequiredColumnsRule(BaseRule):
    """Fails if a required column is absent from the file.

    Optional policy for unexpected columns: set "allow_extra": false to also
    fail when the file has columns that are not in the list. The default is to
    allow them.

    This is a schema rule. It counts columns, not rows: rows_evaluated is the
    number of columns checked, failed_row_count is the number of problems.
    """

    rule_type = "required_columns"
    category = SCHEMA

    def validate_config(self) -> None:
        require_column_list(self.config)
        if not isinstance(self.config.get("allow_extra", True), bool):
            raise ConfigurationError(
                "'allow_extra' must be true or false.", {"field": "allow_extra"}
            )

    def evaluate(self, df: pd.DataFrame) -> RuleResult:
        columns = self.config["columns"]
        allow_extra = self.config.get("allow_extra", True)

        missing = [c for c in columns if c not in df.columns]
        wanted = set(columns)
        unexpected = [] if allow_extra else [c for c in df.columns if c not in wanted]
        details = {
            "columns": columns,
            "missing_columns": missing,
            "allow_extra": allow_extra,
            "unexpected_columns": unexpected,
        }
        examined = len(columns) + len(unexpected)
        problems = len(missing) + len(unexpected)

        if not problems:
            return self._result(
                CheckStatus.PASS,
                "All required columns are present.",
                rows_evaluated=examined,
                details=details,
            )

        parts = []
        if missing:
            parts.append(f"Missing required column(s): {', '.join(missing)}.")
        if unexpected:
            parts.append(f"Unexpected column(s): {', '.join(unexpected)}.")
        return self._result(
            CheckStatus.FAIL,
            " ".join(parts),
            rows_evaluated=examined,
            failed_row_count=problems,
            details=details,
            columns=missing + unexpected,
        )
