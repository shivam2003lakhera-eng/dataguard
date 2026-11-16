import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConfigurationError
from app.models import Dataset, DatasetRecord, QualityResult, QualityRun
from app.services import pipeline
from app.services.pipeline import create_dataset_from_upload, run_quality_checks

# Row 3 has a negative amount, so the rule below rejects it: it must never be loaded.
CSV = b"id,name,amount\n1,Asha,10\n2,Ravi,20\n3,Meena,-5\n"
AMOUNT_RULE = [{
    "name": "amount not negative", "rule_type": "numeric_range", "severity": "MEDIUM",
    "configuration": {"column": "amount", "min": 0},
}]


def upload(db_session, user, content=CSV, keys=("id",), rules=AMOUNT_RULE):
    return create_dataset_from_upload(
        db_session, user.id, content, "d.csv", "D",
        rules=list(rules), key_columns=list(keys) if keys else None,
    )


def rerun(db_session, run, content=CSV):
    return run_quality_checks(db_session, run.dataset_id, content, "d.csv")


def records(db_session) -> dict[str, dict]:
    rows = db_session.scalars(select(DatasetRecord).order_by(DatasetRecord.id)).all()
    return {row.row_key: row.data for row in rows}


def timestamps(db_session) -> dict[str, object]:
    rows = db_session.execute(select(DatasetRecord.row_key, DatasetRecord.updated_at)).all()
    return {key: stamp for key, stamp in rows}


def counts(run) -> tuple:
    return (run.rows_inserted, run.rows_updated, run.rows_unchanged, run.rows_skipped)


def assert_every_valid_row_is_accounted_for(run):
    assert sum(counts(run)) == run.valid_rows


def count(db_session, model) -> int:
    return db_session.scalar(select(func.count()).select_from(model))


# ---------- The basic load ----------

def test_valid_rows_are_loaded_and_rejected_rows_are_not(db_session, user):
    run = upload(db_session, user)
    assert counts(run) == (2, 0, 0, 0)
    assert records(db_session) == {
        '["1"]': {"id": "1", "name": "Asha", "amount": "10"},
        '["2"]': {"id": "2", "name": "Ravi", "amount": "20"},
    }
    assert_every_valid_row_is_accounted_for(run)


def test_nothing_is_stored_without_key_columns(db_session, user):
    run = upload(db_session, user, keys=None)
    assert count(db_session, DatasetRecord) == 0
    assert counts(run) == (None, None, None, None)
    assert db_session.get(Dataset, run.dataset_id).key_columns is None


# ---------- Idempotency: the point of the feature ----------

def test_running_the_same_file_again_changes_nothing(db_session, user):
    first = upload(db_session, user)
    before_data, before_times = records(db_session), timestamps(db_session)

    second = rerun(db_session, first)
    assert counts(second) == (0, 0, 2, 0)
    assert records(db_session) == before_data
    assert timestamps(db_session) == before_times   # not even rewritten
    assert count(db_session, DatasetRecord) == 2
    assert_every_valid_row_is_accounted_for(second)


def test_loading_many_times_never_creates_copies(db_session, user):
    run = upload(db_session, user)
    for _ in range(3):
        run = rerun(db_session, run)
    assert count(db_session, DatasetRecord) == 2


def test_a_changed_row_is_updated_and_the_others_are_untouched(db_session, user):
    first = upload(db_session, user)
    before = timestamps(db_session)

    changed = b"id,name,amount\n1,Asha,10\n2,Ravi Kumar,20\n3,Meena,-5\n"
    second = rerun(db_session, first, changed)
    assert counts(second) == (0, 1, 1, 0)
    assert records(db_session)['["2"]']["name"] == "Ravi Kumar"
    after = timestamps(db_session)
    assert after['["1"]'] == before['["1"]']         # untouched
    assert after['["2"]'] > before['["2"]']          # rewritten


def test_a_new_key_is_inserted_beside_the_existing_ones(db_session, user):
    first = upload(db_session, user)
    more = CSV + b"4,Dev,40\n"
    second = rerun(db_session, first, more)
    assert counts(second) == (1, 0, 2, 0)
    assert count(db_session, DatasetRecord) == 3
    assert_every_valid_row_is_accounted_for(second)


def test_a_loaded_row_that_becomes_invalid_is_left_alone(db_session, user):
    first = upload(db_session, user)
    worse = b"id,name,amount\n1,Asha,-9\n2,Ravi,20\n3,Meena,-5\n"  # row 1 is now rejected
    second = rerun(db_session, first, worse)
    assert counts(second) == (0, 0, 1, 0)
    assert records(db_session)['["1"]']["amount"] == "10"          # the old good version stays
    assert_every_valid_row_is_accounted_for(second)


def test_records_of_different_datasets_do_not_mix(db_session, user):
    first = upload(db_session, user)
    second = upload(db_session, user)   # a second dataset with the same keys
    assert first.dataset_id != second.dataset_id
    assert count(db_session, DatasetRecord) == 4
    for run in (first, second):
        owned = db_session.scalar(
            select(func.count()).select_from(DatasetRecord)
            .where(DatasetRecord.dataset_id == run.dataset_id))
        assert owned == 2


# ---------- Keys and skipped rows ----------

def test_rows_with_a_missing_key_are_skipped(db_session, user):
    run = upload(db_session, user, content=b"id,name,amount\n1,Asha,10\n,Ravi,20\n", rules=[])
    assert counts(run) == (1, 0, 0, 1)
    assert list(records(db_session)) == ['["1"]']
    assert_every_valid_row_is_accounted_for(run)


def test_the_first_row_wins_when_a_key_repeats_in_one_file(db_session, user):
    run = upload(db_session, user, content=b"id,name\n1,First\n1,Second\n", rules=[])
    assert counts(run) == (1, 0, 0, 1)
    assert records(db_session)['["1"]']["name"] == "First"


def test_a_composite_key_loads_one_record_per_combination(db_session, user):
    content = b"id,region,v\n1,N,a\n1,S,b\n1,N,c\n"
    run = upload(db_session, user, content=content, keys=("id", "region"), rules=[])
    assert counts(run) == (2, 0, 0, 1)
    assert set(records(db_session)) == {'["1","N"]', '["1","S"]'}
    assert records(db_session)['["1","N"]']["v"] == "a"


def test_missing_cells_are_stored_as_null_and_values_as_text(db_session, user):
    upload(db_session, user, content=b"id,name,code\n1,   ,007\n2,,1.50\n", rules=[])
    data = records(db_session)
    assert data['["1"]'] == {"id": "1", "name": None, "code": "007"}
    assert data['["2"]'] == {"id": "2", "name": None, "code": "1.50"}


def test_a_key_that_is_too_long_is_skipped(db_session, user):
    content = b"id,v\n" + b"x" * 600 + b",1\nok,2\n"
    run = upload(db_session, user, content=content, rules=[])
    assert counts(run) == (1, 0, 0, 1)


def test_an_unknown_key_column_is_rejected_before_anything_is_saved(db_session, user):
    with pytest.raises(ConfigurationError):
        upload(db_session, user, keys=("nope",))
    assert count(db_session, Dataset) == 0


# ---------- Failures never leave a half-loaded state ----------

def test_a_schema_failure_prevents_loading(db_session, user):
    schema_rule = [{"name": "needs ghost", "rule_type": "required_columns", "severity": "HIGH",
                    "configuration": {"columns": ["id", "ghost"]}}]
    run = upload(db_session, user, rules=schema_rule)
    assert run.loadable is False
    assert counts(run) == (None, None, None, None)
    assert count(db_session, DatasetRecord) == 0


def test_a_key_column_missing_from_a_later_file_is_a_visible_failure(db_session, user):
    first = upload(db_session, user)
    second = rerun(db_session, first, b"name,amount\nA,1\n")
    result = db_session.scalars(
        select(QualityResult).where(QualityResult.run_id == second.id,
                                    QualityResult.rule_name == "Load key columns")).one()
    assert result.status == "FAIL" and result.category == "schema"
    assert result.message.startswith("Configuration error:")
    assert second.loadable is False and second.status == "COMPLETED_WITH_ISSUES"
    assert counts(second) == (None, None, None, None)
    assert count(db_session, DatasetRecord) == 2     # what was loaded before is untouched


def test_a_failure_while_loading_rolls_back_everything(db_session, user, monkeypatch):
    real = pipeline.upsert_records

    def load_then_explode(session, dataset_id, chunks):
        real(session, dataset_id, chunks)   # the rows really are written ...
        raise RuntimeError("boom")          # ... and then the load fails

    monkeypatch.setattr(pipeline, "upsert_records", load_then_explode)
    run = upload(db_session, user)
    assert run.status == "FAILED"
    assert count(db_session, DatasetRecord) == 0           # the partial load was undone
    assert count(db_session, QualityResult) == 0           # and so were the results
    assert run.source_rows is None and counts(run) == (None, None, None, None)
    assert count(db_session, Dataset) == 1                 # the upload itself is kept


# ---------- The database enforces the rules too ----------

def test_the_database_enforces_the_load_accounting(db_session, user):
    dataset_id = upload(db_session, user).dataset_id
    wrong = QualityRun(dataset_id=dataset_id, status="SUCCESS", source_rows=3, valid_rows=3,
                       rejected_rows=0, rows_inserted=1, rows_updated=1, rows_unchanged=1,
                       rows_skipped=1)
    db_session.add(wrong)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    right = QualityRun(dataset_id=dataset_id, status="SUCCESS", source_rows=3, valid_rows=3,
                       rejected_rows=0, rows_inserted=1, rows_updated=1, rows_unchanged=1,
                       rows_skipped=0)
    db_session.add(right)
    db_session.commit()


def test_the_database_enforces_unique_keys_per_dataset(db_session, user):
    dataset_id = upload(db_session, user).dataset_id
    db_session.add(DatasetRecord(dataset_id=dataset_id, row_key='["1"]', data={}))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_deleting_a_dataset_deletes_its_records(db_session, user):
    run = upload(db_session, user)
    db_session.delete(db_session.get(Dataset, run.dataset_id))
    db_session.commit()
    assert count(db_session, DatasetRecord) == 0
