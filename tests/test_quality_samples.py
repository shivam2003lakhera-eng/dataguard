from pathlib import Path

from app.core.constants import CheckStatus
from app.ingestion.csv_reader import read_csv_bytes
from app.quality.engine import run_rules
from app.quality.rules.registry import build_rule

SAMPLES = Path(__file__).resolve().parent.parent / "sample_data"


def load(relative_path: str):
    path = SAMPLES / relative_path
    return read_csv_bytes(path.read_bytes(), path.name)


def check(df, rule_type, config):
    return run_rules(df, [build_rule(rule_type, rule_type, config)])[0]


def test_insurance_planted_problems_are_found():
    df = load("insurance/policies_bad.csv")

    missing = check(df, "required_values", {"columns": ["policy_id"]})
    assert missing.status == CheckStatus.FAIL
    assert missing.failed_row_count == 1

    price = check(df, "numeric_range", {"column": "premium", "min": 0})
    assert price.status == CheckStatus.FAIL
    assert price.failed_row_count == 1  # -850.00

    not_number = check(df, "data_type", {"column": "premium", "data_type": "float"})
    assert not_number.failed_row_count == 1  # 'abc'

    bad_date = check(df, "data_type", {"column": "start_date", "data_type": "date"})
    assert bad_date.failed_row_count == 1  # 'not-a-date'

    status = check(
        df, "allowed_values",
        {"column": "policy_status", "allowed": ["ACTIVE", "EXPIRED", "PENDING"]},
    )
    assert status.failed_row_count == 1  # UNKNOWN

    dupes = check(df, "duplicates", {"columns": ["policy_id"]})
    assert dupes.failed_row_count == 2  # the two P2006 rows


def test_weather_planted_problems_are_found():
    df = load("weather/weather_bad.csv")

    assert check(df, "duplicates", {}).failed_row_count == 2  # the two Mumbai rows
    assert check(df, "required_values", {"columns": ["observation_time"]}).failed_row_count == 1
    assert check(df, "numeric_range", {"column": "humidity", "min": 0, "max": 100}).failed_row_count == 1
    assert check(df, "numeric_range", {"column": "temperature", "min": -50, "max": 60}).failed_row_count == 1
    assert check(df, "numeric_range", {"column": "wind_speed", "min": 0}).failed_row_count == 2


def test_missing_required_column_is_reported():
    df = load("weather/weather_bad.csv")
    result = check(df, "required_columns", {"columns": ["city", "pressure"]})
    assert result.status == CheckStatus.FAIL
    assert result.details["missing_columns"] == ["pressure"]