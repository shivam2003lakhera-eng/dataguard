import json

import pandas as pd

from app.profiling.profiler import profile_dataframe
from app.profiling.statistics import infer_column_type


def get_col(profile: dict, name: str) -> dict:
    """Find one column's profile by name."""
    return next(c for c in profile["columns"] if c["name"] == name)


# ---------- Behavior that already works ----------

def test_basic_counts_and_names():
    df = pd.DataFrame({"id": ["1", "2", "3"], "name": ["a", "b", None]})
    profile = profile_dataframe(df)

    assert profile["row_count"] == 3
    assert profile["column_count"] == 2
    assert [c["name"] for c in profile["columns"]] == ["id", "name"]


def test_missing_count_and_percent():
    df = pd.DataFrame({"name": ["a", "b", None]})
    col = get_col(profile_dataframe(df), "name")

    assert col["null_count"] == 1
    assert col["null_percent"] == 33.33


def test_duplicate_rows_are_counted():
    df = pd.DataFrame({"a": ["1", "1", "2"], "b": ["x", "x", "y"]})

    assert profile_dataframe(df)["duplicate_row_count"] == 1


def test_distinct_count_ignores_missing_values():
    df = pd.DataFrame({"a": ["x", "x", "y", None]})

    assert get_col(profile_dataframe(df), "a")["distinct_count"] == 2


def test_numeric_column_min_max():
    df = pd.DataFrame({"n": ["1", "5.5", "-2"]})
    col = get_col(profile_dataframe(df), "n")

    assert col["inferred_type"] == "numeric"
    assert col["min"] == -2.0
    assert col["max"] == 5.5


def test_mixed_column_uses_only_valid_numbers():
    df = pd.DataFrame({"n": ["10", "abc", "20"]})
    col = get_col(profile_dataframe(df), "n")

    assert col["inferred_type"] == "mixed"
    assert col["min"] == 10.0
    assert col["max"] == 20.0


def test_text_column_has_no_min_max():
    df = pd.DataFrame({"s": ["red", "green"]})
    col = get_col(profile_dataframe(df), "s")

    assert col["inferred_type"] == "text"
    assert col["min"] is None
    assert col["max"] is None


def test_all_missing_column_is_empty():
    df = pd.DataFrame({"x": [None, None]})

    assert get_col(profile_dataframe(df), "x")["inferred_type"] == "empty"


def test_zero_row_dataframe_does_not_crash():
    df = pd.DataFrame({"a": pd.Series([], dtype="str")})
    profile = profile_dataframe(df)

    assert profile["row_count"] == 0
    assert get_col(profile, "a")["null_percent"] == 0.0


def test_profiling_does_not_modify_input():
    df = pd.DataFrame({"a": ["1", None, "x"], "b": ["2025-01-01", "2025-02-01", None]})
    before = df.copy()

    profile_dataframe(df)

    assert df.equals(before)
    assert list(df.columns) == list(before.columns)


# ---------- New behavior we are about to build ----------

def test_iso_dates_are_detected():
    series = pd.Series(["2025-01-01", "2024-06-01", None])

    assert infer_column_type(series) == "date"


def test_iso_datetimes_are_detected():
    series = pd.Series(["2026-10-10T06:00:00", "2026-10-10T09:00:00"])

    assert infer_column_type(series) == "date"


def test_date_column_min_max():
    df = pd.DataFrame({"d": ["2025-01-01", "2024-06-01", "2025-12-31"]})
    col = get_col(profile_dataframe(df), "d")

    assert col["inferred_type"] == "date"
    assert col["min"] == "2024-06-01"
    assert col["max"] == "2025-12-31"
    assert col["mean"] is None


def test_text_that_is_not_all_dates_stays_text():
    series = pd.Series(["2025-01-01", "hello"])

    assert infer_column_type(series) == "text"


def test_year_like_numbers_stay_numeric():
    series = pd.Series(["2003", "2004"])

    assert infer_column_type(series) == "numeric"


def test_infinity_is_not_treated_as_a_number():
    df = pd.DataFrame({"n": ["1", "2", "inf"]})
    col = get_col(profile_dataframe(df), "n")

    assert col["inferred_type"] == "mixed"
    assert col["max"] == 2.0


def test_profile_is_json_safe_even_with_infinity():
    df = pd.DataFrame({"n": ["1", "inf", "-inf"], "d": ["2025-01-01", None, "2025-02-01"]})

    # allow_nan=False raises if any NaN/Infinity sneaks in (PostgreSQL JSONB rejects them)
    json.dumps(profile_dataframe(df), allow_nan=False)