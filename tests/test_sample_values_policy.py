from sqlalchemy import select

from app.core.config import get_settings
from app.models import QualityResult
from app.services.pipeline import create_dataset_from_upload

CSV = b"status,n\nActive,1\nBogus,abc\n"
RULES = [
    {"name": "status allowed", "rule_type": "allowed_values",
     "configuration": {"column": "status", "allowed": ["Active"]}, "severity": "LOW"},
    {"name": "n integer", "rule_type": "data_type",
     "configuration": {"column": "n", "data_type": "integer"}, "severity": "LOW"},
]


def stored_details(db_session) -> dict:
    rows = db_session.scalars(select(QualityResult).order_by(QualityResult.id)).all()
    return {row.rule_name: row.details for row in rows}


def test_raw_values_are_not_stored_by_default(db_session, user):
    create_dataset_from_upload(db_session, user.id, CSV, "d.csv", "D", rules=RULES)
    details = stored_details(db_session)
    assert all("bad_values" not in d for d in details.values())
    assert "Bogus" not in str(details) and "abc" not in str(details)


def test_row_positions_are_still_stored(db_session, user):
    create_dataset_from_upload(db_session, user.id, CSV, "d.csv", "D", rules=RULES)
    details = stored_details(db_session)
    assert details["status allowed"]["sample_row_indexes"] == [1]
    assert details["n integer"]["sample_row_indexes"] == [1]


def test_raw_values_can_be_enabled_explicitly(db_session, user, monkeypatch):
    monkeypatch.setattr(get_settings(), "store_sample_values", True)
    create_dataset_from_upload(db_session, user.id, CSV, "d.csv", "D", rules=RULES)
    details = stored_details(db_session)
    assert details["status allowed"]["bad_values"] == ["Bogus"]
    assert details["n integer"]["bad_values"] == ["abc"]