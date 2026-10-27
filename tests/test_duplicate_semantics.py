from pathlib import Path

import pandas as pd

from app.ingestion.csv_reader import read_csv_bytes
from app.profiling.profiler import profile_dataframe
from app.quality.rules.registry import build_rule

SAMPLES = Path(__file__).resolve().parent.parent / "sample_data"


def full_row_rule(df):
    return build_rule("duplicates", "r", {}).evaluate(df)


def test_profile_reports_extra_copies_rows_involved_and_groups():
    df = pd.DataFrame({"a": ["1", "1", "1", "2"], "b": ["x", "x", "x", "y"]})
    profile = profile_dataframe(df)
    assert profile["duplicate_row_count"] == 2
    assert profile["rows_in_duplicate_groups"] == 3
    assert profile["duplicate_group_count"] == 1


def test_profile_with_two_groups():
    profile = profile_dataframe(pd.DataFrame({"a": ["x", "x", "y", "y", "z"]}))
    assert profile["duplicate_row_count"] == 2
    assert profile["rows_in_duplicate_groups"] == 4
    assert profile["duplicate_group_count"] == 2


def test_profile_without_duplicates_is_all_zero():
    profile = profile_dataframe(pd.DataFrame({"a": ["1", "2", "3"]}))
    assert profile["duplicate_row_count"] == 0
    assert profile["rows_in_duplicate_groups"] == 0
    assert profile["duplicate_group_count"] == 0


def test_rule_reports_the_same_three_numbers_as_the_profile():
    df = pd.DataFrame({"a": ["1", "1", "1", "2"], "b": ["x", "x", "x", "y"]})
    profile, result = profile_dataframe(df), full_row_rule(df)
    assert result.failed_row_count == profile["rows_in_duplicate_groups"] == 3
    assert result.details["extra_copies"] == profile["duplicate_row_count"] == 2
    assert result.details["duplicate_groups"] == profile["duplicate_group_count"] == 1


def test_rule_details_for_key_columns():
    df = pd.DataFrame({"id": ["1", "1", "2"], "v": ["a", "b", "c"]})
    result = build_rule("duplicates", "r", {"columns": ["id"]}).evaluate(df)
    assert result.failed_row_count == 2
    assert result.rows_evaluated == 3
    assert result.details["extra_copies"] == 1
    assert result.details["duplicate_groups"] == 1


def test_profile_and_rule_agree_on_the_weather_sample():
    path = SAMPLES / "weather" / "weather_bad.csv"
    df = read_csv_bytes(path.read_bytes(), path.name)
    profile, result = profile_dataframe(df), full_row_rule(df)
    assert (profile["duplicate_row_count"], profile["rows_in_duplicate_groups"]) == (1, 2)
    assert result.failed_row_count == 2
    assert result.details["extra_copies"] == 1