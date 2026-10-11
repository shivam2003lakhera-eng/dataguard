import time
from collections import Counter

import pandas as pd

from app.core.constants import CheckStatus
from app.core.logging import get_logger
from app.quality.result import RuleResult
from app.quality.rules.base import BaseRule

logger = get_logger(__name__)


def run_rules(df: pd.DataFrame, rules: list[BaseRule]) -> list[RuleResult]:
    """Run every rule on the data and return exactly one result per rule."""
    results: list[RuleResult] = []
    for rule in rules:
        start = time.perf_counter()
        try:
            result = rule.evaluate(df)
        except Exception:
            logger.exception("Rule '%s' crashed", rule.name)
            result = rule._result(
                CheckStatus.FAIL,
                "Rule crashed unexpectedly. See logs.",
                details={"error": "crash"},
            )
        result.duration_ms = round((time.perf_counter() - start) * 1000, 2)
        results.append(result)
    return results


def summarize(results: list[RuleResult]) -> dict[str, int]:
    """Count results by status."""
    counts = Counter(result.status for result in results)
    return {status.value: counts.get(status, 0) for status in CheckStatus}