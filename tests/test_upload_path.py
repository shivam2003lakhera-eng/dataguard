import json
from pathlib import Path

from app.ingestion.csv_reader import read_csv_bytes
from app.profiling.profiler import profile_dataframe

SAMPLES = Path(__file__).resolve().parent.parent / "sample_data"


def profile_sample(relative_path: str) -> dict:
    """Run a sample file through the real upload path: bytes -> reader -> profiler."""
    path = SAMPLES / relative_path
    df = read_csv_bytes(path.read_bytes(), path.name)
    return profile_dataframe(df)


def get_col(profile: dict, name: str) -> dict:
    return next(c for c in profile["columns"] if c["name"] == name)


def test_insurance_bad_sample_end_to_end():
    profile = profile_sample("insurance/policies_bad.csv")

    assert profile["row_count"] == 8
    assert profile["column_count"] == 5
    assert profile["duplicate_row_count"] == 0
    assert get_col(profile, "policy_id")["null_count"] == 1
    assert get_col(profile, "premium")["inferred_type"] == "mixed"
    assert get_col(profile, "start_date")["inferred_type"] == "text"  # has 'not-a-date'
    assert get_col(profile, "end_date")["inferred_type"] == "date"
    assert get_col(profile, "end_date")["min"] == "2023-07-01"
    assert get_col(profile, "end_date")["max"] == "2026-09-01"


def test_weather_bad_sample_end_to_end():
    profile = profile_sample("weather/weather_bad.csv")

    assert profile["row_count"] == 7
    assert profile["duplicate_row_count"] == 1
    assert get_col(profile, "observation_time")["inferred_type"] == "date"
    assert get_col(profile, "humidity")["max"] == 130.0
    assert get_col(profile, "wind_speed")["min"] == -12.3


def test_sample_profiles_are_json_safe():
    for sample in ["insurance/policies_bad.csv", "weather/weather_bad.csv"]:
        json.dumps(profile_sample(sample), allow_nan=False)