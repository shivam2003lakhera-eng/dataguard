import pandas as pd

from app.core.constants import CheckStatus
from app.quality.result import RuleResult
from app.quality.rules.base import BaseRule

MAX_SAMPLES = 5


class DuplicatesRule(BaseRule):
    """Fails if rows repeat, by chosen key columns or across the whole row."""

    rule_type = "duplicates"

    def evaluate(self, df: pd.DataFrame) -> RuleResult:
        columns = self.config.get("columns")

        if columns is None:
            key_columns = list(df.columns)
            label = "full row"
        elif isinstance(columns, list) and columns:
            absent = [col for col in columns if col not in df.columns]
            if absent:
                return self._error(f"Columns not found in data: {absent}")
            key_columns = columns
            label = "key " + ", ".join(columns)
        else:
            return self._error("'columns' must be a non-empty list if given.")

        if not key_columns:
            return self._error("Data has no columns to compare.")

        has_key = df[key_columns].notna().all(axis=1)
        candidates = df[has_key]
        duplicated = candidates.duplicated(subset=key_columns, keep=False)

        failed = int(duplicated.sum())
        details = {"columns": key_columns}

        if failed == 0:
            return self._result(
                CheckStatus.PASS,
                f"No duplicate {label} found.",
                rows_evaluated=len(candidates),
                details=details,
            )

        samples = [int(i) for i in candidates.index[duplicated][:MAX_SAMPLES]]
        return self._result(
            CheckStatus.FAIL,
            f"{failed} row(s) share a duplicate {label}.",
            rows_evaluated=len(candidates),
            failed_row_count=failed,
            sample_row_indexes=samples,
            details=details,
        )