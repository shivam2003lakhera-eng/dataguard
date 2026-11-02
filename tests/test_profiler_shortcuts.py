import pandas as pd

from app.profiling.statistics import DATE_SAMPLE_SIZE, infer_column_type


def test_a_bad_value_after_the_sample_still_makes_the_column_text():
    values = ["2025-01-01"] * (DATE_SAMPLE_SIZE + 500) + ["not-a-date"]
    assert infer_column_type(pd.Series(values)) == "text"


def test_an_impossible_date_after_the_sample_is_still_detected():
    values = ["2025-01-01"] * (DATE_SAMPLE_SIZE + 500) + ["2025-02-30"]
    assert infer_column_type(pd.Series(values)) == "text"


def test_a_long_valid_date_column_is_still_a_date():
    values = ["2025-01-01", "2025-06-30T10:00:00"] * DATE_SAMPLE_SIZE
    assert infer_column_type(pd.Series(values)) == "date"


def test_a_bad_value_inside_the_sample_is_text_without_the_full_parse():
    values = ["x"] + ["2025-01-01"] * (DATE_SAMPLE_SIZE * 2)
    assert infer_column_type(pd.Series(values)) == "text"


def test_numbers_are_still_numbers_and_dates_are_not_confused_with_them():
    assert infer_column_type(pd.Series(["2003", "2004"] * DATE_SAMPLE_SIZE)) == "numeric"
    assert infer_column_type(pd.Series(["1", "2", "abc"] * DATE_SAMPLE_SIZE)) == "mixed"
