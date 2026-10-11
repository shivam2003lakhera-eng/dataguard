from pathlib import Path

import pytest
from sqlalchemy import delete, func, inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.ingestion.csv_reader import read_csv_bytes
from app.models import (
    Dataset,
    DatasetProfile,
    QualityResult,
    QualityRule,
    QualityRun,
)
from app.profiling.profiler import profile_dataframe

SAMPLE = Path(__file__).resolve().parent.parent / "sample_data" / "insurance" / "policies_bad.csv"


def make_dataset(**overrides) -> Dataset:
    values = dict(name="Policies", original_filename="policies.csv", row_count=8, column_count=5)
    values.update(overrides)
    return Dataset(**values)


def count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def build_full_graph(session):
    """One dataset with a profile, a rule, a run and a result."""
    ds = make_dataset()
    rule = QualityRule(
        dataset=ds, name="id required", rule_type="required_values",
        configuration={"columns": ["policy_id"]}, severity="HIGH",
    )
    run = QualityRun(dataset=ds, status="COMPLETED_WITH_ISSUES", checks_passed=0, checks_failed=1)
    session.add_all([
        ds, rule, run,
        DatasetProfile(dataset=ds, profile_data={"row_count": 8}),
    ])
    session.flush()
    result = QualityResult(
        run=run, rule_id=rule.id, rule_name=rule.name, status="FAIL", severity="HIGH",
        rows_evaluated=8, rows_failed=1, message="1 row(s) missing.", details={"columns": ["policy_id"]},
    )
    session.add(result)
    session.commit()
    return ds, rule, run, result


def test_connected_to_the_test_database(db_session):
    assert db_session.scalar(text("select current_database()")) == "dataguard_test"


def test_all_five_tables_exist(test_engine):
    tables = set(inspect(test_engine).get_table_names())
    assert {"datasets", "dataset_profiles", "quality_rules", "quality_runs", "quality_results"} <= tables


def test_save_and_reload_everything(db_session):
    ds, rule, run, result = build_full_graph(db_session)
    db_session.expire_all()

    loaded = db_session.get(Dataset, ds.id)
    assert loaded.name == "Policies"
    assert loaded.created_at is not None
    assert loaded.profiles[0].profile_data == {"row_count": 8}
    assert loaded.rules[0].configuration == {"columns": ["policy_id"]}
    assert loaded.rules[0].enabled is True
    assert loaded.runs[0].started_at is not None
    assert loaded.runs[0].results[0].details == {"columns": ["policy_id"]}


def test_real_profile_round_trips_through_jsonb(db_session):
    profile = profile_dataframe(read_csv_bytes(SAMPLE.read_bytes(), SAMPLE.name))
    ds = make_dataset()
    db_session.add_all([ds, DatasetProfile(dataset=ds, profile_data=profile)])
    db_session.commit()
    db_session.expire_all()

    stored = db_session.scalars(select(DatasetProfile)).one().profile_data
    assert stored == profile


def test_deleting_a_dataset_through_the_orm_removes_children(db_session):
    ds, *_ = build_full_graph(db_session)
    db_session.delete(ds)
    db_session.commit()

    for model in (Dataset, DatasetProfile, QualityRule, QualityRun, QualityResult):
        assert count(db_session, model) == 0


def test_database_level_cascade_works_without_the_orm(db_session):
    build_full_graph(db_session)
    db_session.execute(delete(Dataset))
    db_session.commit()

    for model in (DatasetProfile, QualityRule, QualityRun, QualityResult):
        assert count(db_session, model) == 0


def test_deleting_a_rule_keeps_its_historical_result(db_session):
    _, rule, _, result = build_full_graph(db_session)
    db_session.delete(rule)
    db_session.commit()
    db_session.expire_all()

    kept = db_session.get(QualityResult, result.id)
    assert kept is not None
    assert kept.rule_id is None
    assert kept.rule_name == "id required"


# ---------- Constraints: bad data must be rejected by the database itself ----------

def assert_rejected(session, *objects):
    session.add_all(objects)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_rejects_invalid_rule_severity(db_session):
    ds = make_dataset()
    assert_rejected(db_session, ds, QualityRule(
        dataset=ds, name="r", rule_type="duplicates", configuration={}, severity="CRITICAL"))


def test_rejects_invalid_run_status(db_session):
    ds = make_dataset()
    assert_rejected(db_session, ds, QualityRun(dataset=ds, status="DONE"))


def test_rejects_invalid_result_status(db_session):
    ds = make_dataset()
    run = QualityRun(dataset=ds, status="SUCCESS")
    assert_rejected(db_session, ds, run, QualityResult(
        run=run, rule_name="r", status="WARN", severity="LOW",
        rows_evaluated=1, rows_failed=0, message="m"))


def test_rejects_negative_failed_rows(db_session):
    ds = make_dataset()
    run = QualityRun(dataset=ds, status="SUCCESS")
    assert_rejected(db_session, ds, run, QualityResult(
        run=run, rule_name="r", status="FAIL", severity="LOW",
        rows_evaluated=1, rows_failed=-1, message="m"))


def test_rejects_negative_row_count(db_session):
    assert_rejected(db_session, make_dataset(row_count=-1))


def test_rejects_orphan_profile(db_session):
    assert_rejected(db_session, DatasetProfile(dataset_id=999999, profile_data={}))