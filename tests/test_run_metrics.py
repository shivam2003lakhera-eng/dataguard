import hashlib

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import QualityResult, QualityRule, QualityRun
from app.services import pipeline
from app.services.pipeline import create_dataset_from_upload, run_quality_checks

# Row 1 has a blank id AND a negative amount: it fails two rules but is one rejected row.
CSV = b"id,amount\n1,5\n,-1\n3,7\n"
RULES = [
    {"name": "has columns", "rule_type": "required_columns",
     "configuration": {"columns": ["id", "amount"]}, "severity": "HIGH"},
    {"name": "id required", "rule_type": "required_values",
     "configuration": {"columns": ["id"]}, "severity": "HIGH"},
    {"name": "amount not negative", "rule_type": "numeric_range",
     "configuration": {"column": "amount", "min": 0}, "severity": "MEDIUM"},
]


def upload(db_session, user, rules=RULES, content=CSV):
    return create_dataset_from_upload(db_session, user.id, content, "d.csv", "D", rules=rules)


def results_by_name(db_session):
    rows = db_session.scalars(select(QualityResult).order_by(QualityResult.id)).all()
    return {row.rule_name: row for row in rows}


def test_run_stores_row_accounting_and_metrics(db_session, user):
    run = upload(db_session, user)
    assert run.status == "COMPLETED_WITH_ISSUES"
    assert (run.source_rows, run.valid_rows, run.rejected_rows) == (3, 2, 1)
    assert run.loadable is True
    assert run.duration_ms is not None and run.duration_ms >= 0
    assert run.file_sha256 == hashlib.sha256(CSV).hexdigest()


def test_a_row_failing_two_rules_is_rejected_once(db_session, user):
    upload(db_session, user)
    results = results_by_name(db_session)
    assert results["id required"].rows_rejected == 1
    assert results["amount not negative"].rows_rejected == 1
    assert results["has columns"].rows_rejected == 0


def test_result_category_is_stored(db_session, user):
    upload(db_session, user)
    results = results_by_name(db_session)
    assert results["has columns"].category == "schema"
    assert results["id required"].category == "quality"
    assert results["amount not negative"].category == "quality"


def test_a_rule_on_a_missing_column_is_a_schema_failure_and_rejects_nothing(db_session, user):
    ghost = [{"name": "ghost filled", "rule_type": "required_values",
              "configuration": {"columns": ["ghost"]}, "severity": "LOW"}]
    run = upload(db_session, user, rules=ghost)
    result = results_by_name(db_session)["ghost filled"]
    assert result.category == "schema" and result.rows_rejected == 0
    assert result.message.startswith("Configuration error:")
    assert (run.rejected_rows, run.valid_rows, run.loadable) == (0, 3, False)


def test_a_stored_rule_that_no_longer_builds_is_a_visible_schema_failure(db_session, user):
    first = upload(db_session, user, rules=RULES[1:2])
    rule = db_session.scalars(select(QualityRule)).one()
    rule.configuration = {"columns": []}  # corrupt it directly in the database
    db_session.commit()

    run = run_quality_checks(db_session, first.dataset_id, CSV, "d.csv")
    broken = db_session.scalars(
        select(QualityResult).where(QualityResult.run_id == run.id)).one()
    assert broken.category == "schema" and broken.status == "FAIL"
    assert broken.message.startswith("Configuration error:")
    assert run.loadable is False and run.status == "COMPLETED_WITH_ISSUES"


def test_a_failed_run_records_no_made_up_metrics(db_session, user, monkeypatch):
    first = upload(db_session, user, rules=RULES[1:2])

    def explode(df, rules):
        raise RuntimeError("boom")

    monkeypatch.setattr(pipeline, "run_rules", explode)
    run = run_quality_checks(db_session, first.dataset_id, CSV, "d.csv")
    assert run.status == "FAILED"
    assert run.source_rows is None and run.valid_rows is None and run.rejected_rows is None
    assert run.loadable is None and run.duration_ms is None
    assert run.file_sha256 == hashlib.sha256(CSV).hexdigest()  # the file is still identified


def test_the_same_file_has_the_same_hash_on_every_run(db_session, user):
    first = upload(db_session, user, rules=RULES[1:2])
    second = run_quality_checks(db_session, first.dataset_id, CSV, "other_name.csv")
    other = run_quality_checks(db_session, first.dataset_id, CSV + b"4,9\n", "d.csv")
    assert first.file_sha256 == second.file_sha256 != other.file_sha256


# ---------- The database enforces the same rules ----------

def bad_run(dataset_id, **values):
    return QualityRun(dataset_id=dataset_id, status="SUCCESS", **values)


def assert_rejected(db_session, run):
    db_session.add(run)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_database_rejects_row_counts_that_do_not_add_up(db_session, user):
    dataset_id = upload(db_session, user, rules=[]).dataset_id
    assert_rejected(db_session, bad_run(dataset_id, source_rows=10, valid_rows=5, rejected_rows=4))


def test_database_accepts_row_counts_that_add_up(db_session, user):
    dataset_id = upload(db_session, user, rules=[]).dataset_id
    db_session.add(bad_run(dataset_id, source_rows=10, valid_rows=6, rejected_rows=4))
    db_session.commit()


def test_database_rejects_negative_metrics(db_session, user):
    dataset_id = upload(db_session, user, rules=[]).dataset_id
    assert_rejected(db_session, bad_run(dataset_id, source_rows=-1))
    assert_rejected(db_session, bad_run(dataset_id, duration_ms=-5))
    assert_rejected(db_session, bad_run(dataset_id, source_rows=10, valid_rows=11, rejected_rows=-1))


def test_database_rejects_an_unknown_result_category(db_session, user):
    run = upload(db_session, user, rules=RULES[1:2])
    db_session.add(QualityResult(
        run_id=run.id, rule_name="x", status="FAIL", severity="LOW", category="other",
        rows_evaluated=1, rows_failed=1, message="m"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
