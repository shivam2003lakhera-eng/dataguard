import pandas as pd

from app.core.constants import CheckStatus
from app.core.missing import is_missing
from app.quality.result import RuleResult
from app.quality.rules.base import MAX_SAMPLES, BaseRule, require_column_list


class DuplicatesRule(BaseRule):
    """Fails if rows repeat, across the whole row or by chosen key columns.

    failed_row_count is the number of rows that have an identical twin.
    details also gives duplicate_groups and extra_copies (beyond the first).
    """

    rule_type = "duplicates"

    def validate_config(self) -> None:
        if self.config.get("columns") is not None:
            require_column_list(self.config)

    def evaluate(self, df: pd.DataFrame) -> RuleResult:
        columns = self.config.get("columns")

        if columns is None:
            key_columns = list(df.columns)
            label = "full row"
            candidates = df  # same rows the profiler counts
        else:
            problem = self._absent_columns_failure(df, columns)
            if problem:
                return problem
            key_columns = columns
            label = "key " + ", ".join(columns)
            has_key = ~df[key_columns].apply(is_missing).any(axis=1)
            candidates = df[has_key]  # a missing key is not a duplicate

        involved = candidates.duplicated(subset=key_columns, keep=False)
        extra = candidates.duplicated(subset=key_columns, keep="first")
        failed = int(involved.sum())
        extra_copies = int(extra.sum())
        details = {
            "columns": key_columns,
            "duplicate_groups": failed - extra_copies,
            "extra_copies": extra_copies,
        }

        if failed == 0:
            return self._result(
                CheckStatus.PASS,
                f"No duplicate {label} found.",
                rows_evaluated=len(candidates),
                details=details,
            )
        return self._result(
            CheckStatus.FAIL,
            f"{failed} row(s) share a duplicate {label} "
            f"({failed - extra_copies} group(s), extra copies: {extra_copies}).",
            rows_evaluated=len(candidates),
            failed_row_count=failed,
            sample_row_indexes=[int(i) for i in candidates.index[involved][:MAX_SAMPLES]],
            details=details,
        )