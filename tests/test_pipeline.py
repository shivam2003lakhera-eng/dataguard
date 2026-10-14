from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.core.exceptions import ConfigurationError, InvalidSourceDataError
from app.models import Dataset, DatasetProfile, QualityResult, QualityRule, QualityRun
from app.services.pipeline import create_dataset_from_upload, run_quality_checks

SAMPLES = Path(__file__).resolve().parent.parent / "sample_data"
BAD = (SAMPLES / "insurance" / "policies_bad.csv").read_bytes()
CLEAN = (SAMPLES / "insurance" / "policies_clean.csv").read_bytes()

ID_REQUIRED = {
    "name": "id required", "rule_type": "required_values",
    "configuration": {"columns": ["policy_id"]}, "severity": "HIGH",
}


def count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def test_upload_saves_dataset_profile_and_run(db_session):
    run = create_dataset_from_upload(db_session, BAD, "policies_bad.csv", "Policies", rules=[ID_REQUIRED])

    assert run.status == "COMPLETED_WITH_ISSUES"
    assert run.checks_failed == 1 and run.checks_passed == 0
    assert run.completed_at is not None

    dataset = db_session.get(Dataset, run.dataset_id)
    assert dataset.name == "Policies"
    assert dataset.original_filename == "policies_bad.csv"
    assert dataset.row_count == 8 and dataset.column_count == 5
    assert count(db_session, DatasetProfile) == 1
    assert count(db_session, QualityRule) == 1
    assert count(db_session, QualityResult) == 1


def test_result_is_stored_with_rule_link_and_counts(db_session):
    run = create_dataset_from_upload(db_session, BAD, "p.csv", "P", rules=[ID_REQUIRED])
    result = db_session.scalars(select(QualityResult)).one()
    rule = db_session.scalars(select(QualityRule)).one()

    assert result.run_id == run.id
    assert result.rule_id == rule.id
    assert result.rule_name == "id required"
    assert result.status == "FAIL" and result.severity == "HIGH"
    assert result.rows_evaluated == 8 and result.rows_failed == 1


def test_all_checks_passing_gives_success(db_session):
    rule = {"name": "has id", "rule_type": "required_columns",
            "configuration": {"columns": ["policy_id"]}, "severity": "LOW"}
    run = create_dataset_from_upload(db_session, CLEAN, "clean.csv", "Clean", rules=[rule])

    assert run.status == "SUCCESS"
    assert run.checks_passed == 1 and run.checks_failed == 0


def test_upload_without_rules_is_success_with_zero_checks(db_session):
    run = create_dataset_from_upload(db_session, CLEAN, "clean.csv", "Clean")

    assert run.status == "SUCCESS"
    assert run.checks_passed == 0 and run.checks_failed == 0
    assert count(db_session, DatasetProfile) == 1


def test_invalid_csv_saves_nothing(db_session):
    with pytest.raises(InvalidSourceDataError):
        create_dataset_from_upload(db_session, b"", "empty.csv", "Empty")

    for model in (Dataset, DatasetProfile, QualityRule, QualityRun, QualityResult):
        assert count(db_session, model) == 0


def test_invalid_rule_config_saves_nothing(db_session):
    bad_rule = {"name": "bad", "rule_type": "numeric_range",
                "configuration": {"column": "premium"}, "severity": "LOW"}
    with pytest.raises(ConfigurationError):
        create_dataset_from_upload(db_session, BAD, "p.csv", "P", rules=[bad_rule])

    assert count(db_session, Dataset) == 0
    assert count(db_session, QualityRule) == 0


def test_second_run_uses_a_new_file_and_adds_history(db_session):
    first = create_dataset_from_upload(db_session, BAD, "p.csv", "P", rules=[ID_REQUIRED])
    second = run_quality_checks(db_session, first.dataset_id, CLEAN, "clean.csv")

    assert second.id != first.id
    assert second.dataset_id == first.dataset_id
    assert second.status == "SUCCESS"
    assert count(db_session, QualityRun) == 2
    assert count(db_session, QualityResult) == 2


def test_disabled_rules_are_not_run(db_session):
    first = create_dataset_from_upload(db_session, BAD, "p.csv", "P", rules=[ID_REQUIRED])
    rule = db_session.scalars(select(QualityRule)).one()
    rule.enabled = False
    db_session.commit()

    second = run_quality_checks(db_session, first.dataset_id, BAD, "p.csv")
    assert second.checks_passed == 0 and second.checks_failed == 0
    assert second.status == "SUCCESS"


def test_run_against_unknown_dataset_raises_not_found(db_session):
    from app.core.exceptions import NotFoundError
    with pytest.raises(NotFoundError):
        run_quality_checks(db_session, 999999, CLEAN, "clean.csv")


def test_invalid_file_on_rerun_creates_no_run(db_session):
    first = create_dataset_from_upload(db_session, BAD, "p.csv", "P")
    with pytest.raises(InvalidSourceDataError):
        run_quality_checks(db_session, first.dataset_id, b"", "empty.csv")

    assert count(db_session, QualityRun) == 1


def test_unexpected_crash_marks_run_failed_and_hides_details(db_session, monkeypatch):
    import app.services.pipeline as pipeline

    first = create_dataset_from_upload(db_session, BAD, "p.csv", "P")

    def explode(df, rules):
        raise RuntimeError("secret internal detail F:\\server\\path")

    monkeypatch.setattr(pipeline, "run_rules", explode)
    run = run_quality_checks(db_session, first.dataset_id, BAD, "p.csv")

    assert run.status == "FAILED"
    assert run.completed_at is not None
    assert run.error_message
    assert "secret" not in run.error_message and "F:" not in run.error_message
    db_session.expire_all()
    stored = db_session.get(QualityRun, run.id)
    assert stored.status == "FAILED"


def test_a_failed_run_keeps_no_partial_results(db_session, monkeypatch):
    import app.services.pipeline as pipeline

    first = create_dataset_from_upload(db_session, BAD, "p.csv", "P", rules=[ID_REQUIRED])
    before = count(db_session, QualityResult)

    monkeypatch.setattr(pipeline, "run_rules", lambda df, rules: (_ for _ in ()).throw(RuntimeError("x")))
    run = run_quality_checks(db_session, first.dataset_id, BAD, "p.csv")

    assert run.status == "FAILED"
    assert count(db_session, QualityResult) == before