"""The data pipeline, independent of FastAPI and of the database.

    CSV bytes -> extract -> profile -> validate -> separate valid / rejected rows -> report

process_dataframe() is the pure core: a DataFrame and some rules in, a report out.
run_pipeline() wraps it for a file on disk and never raises: whatever happens, it
returns a report, and a pipeline failure is never reported as success.
"""
import time
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import get_settings
from app.core.constants import RunStatus
from app.core.exceptions import ConfigurationError, DataGuardError, FileTooLargeError
from app.core.logging import get_logger
from app.ingestion.csv_reader import read_csv_bytes
from app.processing.report import PipelineReport, RejectedRow, RuleSummary
from app.profiling.profiler import profile_dataframe
from app.quality.engine import run_rules
from app.quality.result import QUALITY, SCHEMA
from app.quality.rules.base import BaseRule
from app.quality.rules.registry import build_rule

logger = get_logger(__name__)

DEFAULT_MAX_MB = 50
DEFAULT_MAX_REJECTED_LISTED = 200
UNEXPECTED_ERROR_MESSAGE = "The pipeline failed unexpectedly. See the log for details."


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def _ms(since: float) -> float:
    return round((time.perf_counter() - since) * 1000, 2)


def _default_max_bytes() -> int:
    """The upload limit from the settings, or 50 MB when no settings exist.

    The command-line tool must work without a database configured, so a missing
    or invalid .env falls back to the default instead of failing.
    """
    try:
        return get_settings().max_file_size_mb * 1024 * 1024
    except Exception:
        return DEFAULT_MAX_MB * 1024 * 1024


def build_rules(specs: list[dict[str, Any]]) -> list[BaseRule]:
    """Turn rule dictionaries into validated rules, or raise ConfigurationError.

    Configuration is checked here, before any data is read, so a malformed rule
    is reported as a configuration error and never as a data quality failure.
    """
    if not isinstance(specs, list):
        raise ConfigurationError("Rules must be a list of rule objects.")
    rules = []
    for number, spec in enumerate(specs, start=1):
        if not isinstance(spec, dict):
            raise ConfigurationError(f"Rule {number} must be an object.")
        name = spec.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ConfigurationError(f"Rule {number} needs a non-empty 'name'.")
        rules.append(build_rule(
            spec.get("rule_type", ""),
            name.strip(),
            spec.get("configuration", {}),
            spec.get("severity", "MEDIUM"),
        ))
    return rules


def process_dataframe(
    df: pd.DataFrame,
    rules: list[BaseRule],
    *,
    run_id: str | None = None,
    source_file: str | None = None,
    max_rejected_listed: int = DEFAULT_MAX_REJECTED_LISTED,
    timings: dict[str, float] | None = None,
) -> PipelineReport:
    """Profile the data, run the rules, and separate valid from rejected rows.

    The DataFrame is only read, never modified.
    """
    started = time.perf_counter()
    timings = dict(timings or {})

    step = time.perf_counter()
    profile = profile_dataframe(df)
    timings["profile"] = _ms(step)

    step = time.perf_counter()
    results = run_rules(df, rules)
    timings["validate"] = _ms(step)

    step = time.perf_counter()
    quality = [r for r in results if r.category == QUALITY]

    # Valid and rejected rows. A row failing several rules is counted once.
    rejected: set[int] = set()
    per_rule_total = 0
    for result in quality:
        per_rule_total += len(result.rejected_index)
        rejected.update(result.rejected_index)

    failed = [r for r in results if r.status.value == "FAIL"]
    schema_failures = sum(1 for r in failed if r.category == SCHEMA)
    quality_failures = len(failed) - schema_failures

    # A few examples of rejected rows, each with its rule and reason (no cell values).
    pairs = [(index, result) for result in quality for index in result.rejected_index[:max_rejected_listed]]
    pairs.sort(key=lambda pair: (pair[0], pair[1].rule_name))
    listed = pairs[:max_rejected_listed]

    report = PipelineReport(
        run_id=run_id or new_run_id(),
        status=(RunStatus.COMPLETED_WITH_ISSUES if failed else RunStatus.SUCCESS).value,
        source_file=source_file,
        source_rows=len(df),
        source_columns=len(df.columns),
        valid_rows=len(df) - len(rejected),
        rejected_rows=len(rejected),
        duplicate_rows=profile["duplicate_row_count"],
        overlap_rows=per_rule_total - len(rejected),
        rules_executed=len(results),
        rules_passed=len(results) - len(failed),
        rules_failed=len(failed),
        schema_failures=schema_failures,
        quality_failures=quality_failures,
        rules_crashed=sum(1 for r in results if r.details.get("error") == "crash"),
        loadable=schema_failures == 0,
        rules=[
            RuleSummary(
                name=r.rule_name, rule_type=r.rule_type, category=r.category,
                severity=r.severity.value, status=r.status.value,
                rows_evaluated=r.rows_evaluated, rows_failed=r.failed_row_count,
                rows_rejected=len(r.rejected_index), columns=list(r.columns), message=r.message,
            )
            for r in results
        ],
        rejected_sample=[
            RejectedRow(
                row_index=int(index), data_row=int(index) + 1, rule=result.rule_name,
                rule_type=result.rule_type, columns=list(result.columns), reason=result.reason,
            )
            for index, result in listed
        ],
        rejected_sample_truncated=per_rule_total > len(listed),
        profile=profile,
    )
    timings["report"] = _ms(step)
    report.timings_ms = timings
    report.duration_ms = _ms(started) + sum(
        value for key, value in timings.items() if key not in ("profile", "validate", "report")
    )
    return report


def _failed_report(
    run_id: str, source_file: str | None, started: float,
    timings: dict[str, float], code: str, message: str,
) -> PipelineReport:
    """A FAILED report. Counts that were never measured stay None."""
    return PipelineReport(
        run_id=run_id,
        status=RunStatus.FAILED.value,
        source_file=source_file,
        loadable=False,
        duration_ms=_ms(started),
        timings_ms=timings,
        error={"code": code, "message": message},
    )


def run_pipeline(
    input_path: str | Path,
    rules: list[dict[str, Any]] | None = None,
    *,
    max_bytes: int | None = None,
    max_rejected_listed: int = DEFAULT_MAX_REJECTED_LISTED,
) -> PipelineReport:
    """Run the whole pipeline on a CSV file and return a structured report.

    Never raises. Input problems, bad rule configuration and unexpected errors
    all come back as a report with status FAILED and an error code. Error
    messages never contain file paths or cell values.
    """
    started = time.perf_counter()
    run_id = new_run_id()
    path = Path(input_path)
    timings: dict[str, float] = {}
    try:
        built = build_rules(rules or [])  # configuration first: cheap, and needs no data
        limit = _default_max_bytes() if max_bytes is None else max_bytes

        step = time.perf_counter()
        size = path.stat().st_size
        if size > limit:  # refuse before reading a huge file into memory
            raise FileTooLargeError(
                "File exceeds the maximum allowed size.",
                {"filename": path.name, "limit_mb": round(limit / (1024 * 1024), 2)},
            )
        df = read_csv_bytes(path.read_bytes(), path.name, max_bytes=limit)
        timings["extract"] = _ms(step)

        report = process_dataframe(
            df, built, run_id=run_id, source_file=path.name,
            max_rejected_listed=max_rejected_listed, timings=timings,
        )
        report.duration_ms = _ms(started)  # the whole run, including reading the file
        return report
    except DataGuardError as exc:
        return _failed_report(run_id, path.name, started, timings, exc.code, exc.message)
    except OSError:
        # FileNotFoundError, PermissionError, IsADirectoryError ... The system
        # message contains the path, so we report a fixed message instead.
        return _failed_report(
            run_id, path.name, started, timings,
            "source_file_not_found", "The input file could not be read.",
        )
    except Exception:
        logger.exception("Pipeline run %s failed", run_id)
        return _failed_report(
            run_id, path.name, started, timings, "internal_error", UNEXPECTED_ERROR_MESSAGE
        )
