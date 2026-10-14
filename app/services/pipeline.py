from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import RunStatus
from app.core.exceptions import ConfigurationError, NotFoundError
from app.core.logging import get_logger
from app.ingestion.csv_reader import read_csv_bytes
from app.models import (
    Dataset,
    DatasetProfile,
    QualityResult,
    QualityRule,
    QualityRun,
)
from app.profiling.profiler import profile_dataframe
from app.quality.engine import run_rules
from app.quality.rules.registry import build_rule

logger = get_logger(__name__)

RUN_FAILED_MESSAGE = "The quality run failed unexpectedly. See server logs."


def _validate_rule_specs(rules: list[dict[str, Any]]) -> None:
    """Raise ConfigurationError before anything is saved."""
    for spec in rules:
        build_rule(
            spec.get("rule_type", ""),
            spec.get("name", ""),
            spec.get("configuration", {}),
            spec.get("severity", "MEDIUM"),
        )


def _load_rule_objects(session: Session, dataset_id: int):
    """Return (stored_rule, built_rule) pairs for enabled rules.

    A stored rule that no longer builds is skipped here and reported by the caller
    as a visible failure, never silently dropped.
    """
    stored = session.scalars(
        select(QualityRule)
        .where(QualityRule.dataset_id == dataset_id, QualityRule.enabled.is_(True))
        .order_by(QualityRule.id)
    ).all()
    pairs, broken = [], []
    for rule in stored:
        try:
            pairs.append((rule, build_rule(rule.rule_type, rule.name, rule.configuration, rule.severity)))
        except ConfigurationError as exc:
            broken.append((rule, exc.message))
    return pairs, broken


def _execute_run(session: Session, run: QualityRun, df) -> QualityRun:
    """Run the checks and persist the outcome. Never raises for pipeline errors."""
    try:
        pairs, broken = _load_rule_objects(session, run.dataset_id)
        results = run_rules(df, [built for _, built in pairs])

        rows = []
        for (stored, _), result in zip(pairs, results):
            rows.append(QualityResult(
                run_id=run.id, rule_id=stored.id, rule_name=result.rule_name,
                status=result.status.value, severity=result.severity.value,
                rows_evaluated=result.rows_evaluated, rows_failed=result.failed_row_count,
                message=result.message,
                details={**result.details, "sample_row_indexes": result.sample_row_indexes},
            ))
        for stored, message in broken:
            rows.append(QualityResult(
                run_id=run.id, rule_id=stored.id, rule_name=stored.name,
                status="FAIL", severity=stored.severity, rows_evaluated=0, rows_failed=0,
                message=f"Configuration error: {message}", details={"error": "configuration"},
            ))

        failed = sum(1 for r in rows if r.status == "FAIL")
        session.add_all(rows)
        run.checks_failed = failed
        run.checks_passed = len(rows) - failed
        run.status = (RunStatus.COMPLETED_WITH_ISSUES if failed else RunStatus.SUCCESS).value
        run.error_message = None
        run.completed_at = datetime.now(UTC)
        session.commit()
    except Exception:
        logger.exception("Quality run %s failed", run.id)
        session.rollback()
        run = session.get(QualityRun, run.id)
        run.status = RunStatus.FAILED.value
        run.error_message = RUN_FAILED_MESSAGE
        run.checks_passed = 0
        run.checks_failed = 0
        run.completed_at = datetime.now(UTC)
        session.commit()
    return run


def _start_run(session: Session, dataset_id: int) -> QualityRun:
    """Commit a run row that starts as FAILED, so an interrupted run never looks successful."""
    run = QualityRun(
        dataset_id=dataset_id, status=RunStatus.FAILED.value,
        error_message="Run did not finish.", checks_passed=0, checks_failed=0,
    )
    session.add(run)
    session.commit()
    return run


def create_dataset_from_upload(
    session: Session,
    content: bytes,
    filename: str,
    name: str,
    description: str | None = None,
    rules: list[dict[str, Any]] | None = None,
) -> QualityRun:
    """Upload pipeline: validate, save dataset/profile/rules, run the first check."""
    rules = rules or []
    df = read_csv_bytes(content, filename)  # raises before anything is saved
    _validate_rule_specs(rules)             # raises before anything is saved
    profile = profile_dataframe(df)

    try:
        dataset = Dataset(
            name=name, description=description, original_filename=_clean_name(filename),
            row_count=len(df), column_count=len(df.columns),
        )
        session.add(dataset)
        session.add(DatasetProfile(dataset=dataset, profile_data=profile))
        for spec in rules:
            session.add(QualityRule(
                dataset=dataset, name=spec["name"], rule_type=spec["rule_type"],
                configuration=spec.get("configuration", {}),
                severity=str(spec.get("severity", "MEDIUM")).upper(),
            ))
        session.commit()
    except Exception:
        session.rollback()
        raise

    return _execute_run(session, _start_run(session, dataset.id), df)


def run_quality_checks(session: Session, dataset_id: int, content: bytes, filename: str) -> QualityRun:
    """Re-validate a newly uploaded file against the dataset's stored rules."""
    if session.get(Dataset, dataset_id) is None:
        raise NotFoundError("Dataset not found.", {"dataset_id": dataset_id})
    df = read_csv_bytes(content, filename)  # raises before a run row exists
    return _execute_run(session, _start_run(session, dataset_id), df)


def _clean_name(filename: str) -> str:
    return filename.replace("\\", "/").split("/")[-1]