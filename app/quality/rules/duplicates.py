import pandas as pd

from app.core.constants import CheckStatus
from app.quality.result import RuleResult
from app.quality.rules.base import MAX_SAMPLES, BaseRule, require_column_list


class DuplicatesRule(BaseRule):
    """Fails if rows repeat, across the whole row or by chosen key columns."""

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
            candidates = df[df[key_columns].notna().all(axis=1)]  # blank keys are not duplicates

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
        return self._result(
            CheckStatus.FAIL,
            f"{failed} row(s) share a duplicate {label}.",
            rows_evaluated=len(candidates),
            failed_row_count=failed,
            sample_row_indexes=[int(i) for i in candidates.index[duplicated][:MAX_SAMPLES]],
            details=details,
        )