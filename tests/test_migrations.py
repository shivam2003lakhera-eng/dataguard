from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint, inspect, text

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app.db.base import Base

ROOT = Path(__file__).resolve().parent.parent
MODEL_TABLES = set(Base.metadata.tables)


def alembic_config(url: str | None = None) -> Config:
    config = Config()  # no .ini file, so the app's logging setup is left alone
    config.set_main_option("script_location", str(ROOT / "migrations"))
    if url:
        config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


def database_url(engine) -> str:
    return engine.url.render_as_string(hide_password=False)


def wipe(engine) -> None:
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))


def restore_model_schema(engine) -> None:
    """Put the test database back the way the other tests expect it."""
    wipe(engine)
    Base.metadata.create_all(engine)


def only_model_objects(obj, name, type_, reflected, compare_to) -> bool:
    return not (type_ == "table" and name == "alembic_version")


@pytest.fixture
def migrated(test_engine):
    """The test database, rebuilt from the migrations only."""
    wipe(test_engine)
    config = alembic_config(database_url(test_engine))
    try:
        command.upgrade(config, "head")
        yield config, test_engine
    finally:
        restore_model_schema(test_engine)


def test_upgrade_creates_every_model_table(migrated):
    _, engine = migrated
    assert MODEL_TABLES <= set(inspect(engine).get_table_names())


def test_migrated_schema_matches_the_models(migrated):
    _, engine = migrated
    with engine.connect() as conn:
        context = MigrationContext.configure(
            conn, opts={"compare_type": True, "include_object": only_model_objects}
        )
        differences = compare_metadata(context, Base.metadata)
    assert differences == [], f"models and migrations disagree: {differences}"


def test_check_constraints_match_the_models(migrated):
    _, engine = migrated
    inspector = inspect(engine)
    for table in Base.metadata.tables.values():
        expected = {c.name for c in table.constraints if isinstance(c, CheckConstraint) and c.name}
        actual = {c["name"] for c in inspector.get_check_constraints(table.name)}
        assert expected == actual, table.name


def test_there_is_a_single_migration_head():
    assert len(ScriptDirectory.from_config(alembic_config()).get_heads()) == 1


def test_upgrade_can_be_repeated(migrated):
    config, engine = migrated
    command.upgrade(config, "head")
    assert MODEL_TABLES <= set(inspect(engine).get_table_names())


def test_downgrade_to_base_removes_the_tables(migrated):
    config, engine = migrated
    command.downgrade(config, "base")
    assert not (MODEL_TABLES & set(inspect(engine).get_table_names()))


def test_downgrade_one_step_then_upgrade_again(migrated):
    config, engine = migrated
    command.downgrade(config, "0001_baseline")
    columns = {c["name"] for c in inspect(engine).get_columns("quality_runs")}
    assert "source_rows" not in columns and "file_sha256" not in columns
    command.upgrade(config, "head")
    columns = {c["name"] for c in inspect(engine).get_columns("quality_runs")}
    assert {"source_rows", "valid_rows", "rejected_rows", "duration_ms", "loadable", "file_sha256"} <= columns


def test_upgrade_keeps_and_classifies_existing_results(test_engine):
    """A database that already holds data is upgraded without losing any of it."""
    wipe(test_engine)
    config = alembic_config(database_url(test_engine))
    try:
        command.upgrade(config, "0001_baseline")
        with test_engine.begin() as conn:
            user_id = conn.execute(text(
                "INSERT INTO users (email, password_hash) VALUES ('legacy@example.com', 'x') RETURNING id"
            )).scalar_one()
            dataset_id = conn.execute(text(
                "INSERT INTO datasets (user_id, name, original_filename, row_count, column_count) "
                "VALUES (:u, 'd', 'd.csv', 1, 1) RETURNING id"), {"u": user_id}).scalar_one()
            rule_ids = {}
            for rule_type in ("required_columns", "required_values"):
                rule_ids[rule_type] = conn.execute(text(
                    "INSERT INTO quality_rules (dataset_id, name, rule_type, configuration, severity) "
                    "VALUES (:d, :t, :t, CAST('{}' AS JSONB), 'LOW') RETURNING id"),
                    {"d": dataset_id, "t": rule_type}).scalar_one()
            run_id = conn.execute(text(
                "INSERT INTO quality_runs (dataset_id, status) VALUES (:d, 'SUCCESS') RETURNING id"),
                {"d": dataset_id}).scalar_one()
            for name, rule_type, details in [
                ("config failure", "required_values", '{"error": "configuration"}'),
                ("columns", "required_columns", "{}"),
                ("values", "required_values", "{}"),
            ]:
                conn.execute(text(
                    "INSERT INTO quality_results (run_id, rule_id, rule_name, status, severity, "
                    "rows_evaluated, rows_failed, message, details) "
                    "VALUES (:r, :rule, :n, 'FAIL', 'LOW', 1, 1, 'm', CAST(:d AS JSONB))"),
                    {"r": run_id, "rule": rule_ids[rule_type], "n": name, "d": details})

        command.upgrade(config, "head")

        with test_engine.connect() as conn:
            categories = dict(conn.execute(text("SELECT rule_name, category FROM quality_results")).all())
            unknown_rejected = conn.execute(text(
                "SELECT count(*) FROM quality_results WHERE rows_rejected IS NOT NULL")).scalar_one()
            old_run = conn.execute(text(
                "SELECT source_rows, valid_rows, rejected_rows, loadable, file_sha256 FROM quality_runs"
            )).one()
        assert categories == {"config failure": "schema", "columns": "schema", "values": "quality"}
        assert unknown_rejected == 0              # old results: rejected rows were not recorded
        assert tuple(old_run) == (None, None, None, None, None)  # old runs: not measured, not zero
    finally:
        restore_model_schema(test_engine)


def test_the_record_loading_migration_can_be_reversed_and_reapplied(migrated):
    config, engine = migrated
    command.downgrade(config, "0002_run_metrics")
    inspector = inspect(engine)
    assert "dataset_records" not in inspector.get_table_names()
    assert "key_columns" not in {c["name"] for c in inspector.get_columns("datasets")}
    assert "rows_inserted" not in {c["name"] for c in inspector.get_columns("quality_runs")}

    command.upgrade(config, "head")
    inspector = inspect(engine)
    assert "dataset_records" in inspector.get_table_names()
    assert "key_columns" in {c["name"] for c in inspector.get_columns("datasets")}
