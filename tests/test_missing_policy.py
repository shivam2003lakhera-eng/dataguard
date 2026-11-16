import pandas as pd

from app.core.missing import is_missing
from app.profiling.profiler import profile_dataframe
from app.profiling.statistics import infer_column_type
from app.quality.rules.registry import build_rule


def get_col(profile: dict, name: str) -> dict:
    return next(c for c in profile["columns"] if c["name"] == name)


def evaluate(rule_type, config, df):
    return build_rule(rule_type, "r", config).evaluate(df)


def test_is_missing_flags_none_nan_empty_and_whitespace():
    series = pd.Series(["a", None, "", "   ", "\t", float("nan"), " b "])
    assert is_missing(series).tolist() == [False, True, True, True, True, True, False]


def test_profile_and_required_values_agree_on_what_is_missing():
    df = pd.DataFrame({"name": ["Asha", "   ", None, ""]})
    from_profile = get_col(profile_dataframe(df), "name")["null_count"]
    from_rule = evaluate("required_values", {"columns": ["name"]}, df).failed_row_count
    assert from_profile == from_rule == 3


def test_missing_percent_uses_the_shared_definition():
    col = get_col(profile_dataframe(pd.DataFrame({"name": ["a", "  ", "", None]})), "name")
    assert col["null_count"] == 3
    assert col["null_percent"] == 75.0


def test_type_inference_ignores_whitespace_only_cells():
    assert infer_column_type(pd.Series(["1", "2", "   "])) == "numeric"
    assert infer_column_type(pd.Series(["2025-01-01", "  ", None])) == "date"


def test_distinct_count_ignores_missing_and_whitespace():
    col = get_col(profile_dataframe(pd.DataFrame({"s": ["x", "x", "  ", None, ""]})), "s")
    assert col["distinct_count"] == 1


def test_allowed_values_skips_blank_and_whitespace_cells():
    df = pd.DataFrame({"s": ["Active", "  ", None, ""]})
    result = evaluate("allowed_values", {"column": "s", "allowed": ["Active"]}, df)
    assert result.status.value == "PASS"
    assert result.rows_evaluated == 1


def test_data_type_skips_blank_and_whitespace_cells():
    df = pd.DataFrame({"n": ["1", "  ", None, ""]})
    result = evaluate("data_type", {"column": "n", "data_type": "integer"}, df)
    assert result.status.value == "PASS"
    assert result.rows_evaluated == 1


def test_duplicate_key_ignores_blank_and_whitespace_keys():
    df = pd.DataFrame({"id": ["1", "  ", "  ", "1", ""], "v": list("abcde")})
    result = evaluate("duplicates", {"columns": ["id"]}, df)
    assert result.failed_row_count == 2
    assert result.rows_evaluated == 2