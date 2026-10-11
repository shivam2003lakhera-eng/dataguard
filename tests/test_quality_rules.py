import pandas as pd
import pytest

from app.core.constants import CheckStatus, Severity
from app.core.exceptions import ConfigurationError
from app.quality.engine import run_rules, summarize
from app.quality.rules.registry import build_rule


def run(rule_type, config, df, severity="MEDIUM"):
    """Build one rule and evaluate it against df."""
    return build_rule(rule_type, "test_rule", config, severity).evaluate(df)


# ---------- Enums ----------

def test_severity_values_match_spec():
    assert [s.value for s in Severity] == ["LOW", "MEDIUM", "HIGH"]


def test_status_values_match_spec():
    assert [s.value for s in CheckStatus] == ["PASS", "FAIL"]


def test_default_severity_is_medium():
    rule = build_rule("required_values", "r", {"columns": ["id"]})
    assert rule.severity == Severity.MEDIUM


def test_severity_is_carried_into_result():
    df = pd.DataFrame({"id": ["1", None]})
    result = run("required_values", {"columns": ["id"]}, df, severity="HIGH")
    assert result.severity == Severity.HIGH


# ---------- 1. required_columns ----------

def test_required_columns_pass():
    df = pd.DataFrame({"id": ["1"], "name": ["a"]})
    result = run("required_columns", {"columns": ["id", "name"]}, df)
    assert result.status == CheckStatus.PASS


def test_required_columns_fail_lists_missing():
    df = pd.DataFrame({"id": ["1"]})
    result = run("required_columns", {"columns": ["id", "email"]}, df)
    assert result.status == CheckStatus.FAIL
    assert result.details["missing_columns"] == ["email"]


# ---------- 2. required_values (no missing values) ----------

def test_required_values_pass():
    df = pd.DataFrame({"id": ["1", "2"]})
    result = run("required_values", {"columns": ["id"]}, df)
    assert result.status == CheckStatus.PASS
    assert result.rows_evaluated == 2
    assert result.failed_row_count == 0


def test_required_values_fail_counts_blank_and_missing():
    df = pd.DataFrame({"id": ["1", None, "  ", "4"]})
    result = run("required_values", {"columns": ["id"]}, df)
    assert result.status == CheckStatus.FAIL
    assert result.rows_evaluated == 4
    assert result.failed_row_count == 2
    assert "2" in result.message


# ---------- 3. duplicates ----------

def test_duplicates_full_row_pass():
    df = pd.DataFrame({"a": ["1", "2"], "b": ["x", "x"]})
    assert run("duplicates", {}, df).status == CheckStatus.PASS


def test_duplicates_full_row_fail():
    df = pd.DataFrame({"a": ["1", "1", "2"], "b": ["x", "x", "y"]})
    result = run("duplicates", {}, df)
    assert result.status == CheckStatus.FAIL
    assert result.failed_row_count == 2


def test_duplicates_by_key_column():
    df = pd.DataFrame({"id": ["1", "1", "2"], "v": ["a", "b", "c"]})
    result = run("duplicates", {"columns": ["id"]}, df)
    assert result.status == CheckStatus.FAIL
    assert result.failed_row_count == 2


# ---------- 4. numeric_range ----------

def test_numeric_range_pass():
    df = pd.DataFrame({"age": ["0", "50", "120"]})
    result = run("numeric_range", {"column": "age", "min": 0, "max": 120}, df)
    assert result.status == CheckStatus.PASS
    assert result.rows_evaluated == 3


def test_numeric_range_fail():
    df = pd.DataFrame({"age": ["10", "-5", "200"]})
    result = run("numeric_range", {"column": "age", "min": 0, "max": 120}, df)
    assert result.status == CheckStatus.FAIL
    assert result.failed_row_count == 2
    assert result.rows_evaluated == 3


def test_numeric_range_only_min_is_allowed():
    df = pd.DataFrame({"x": ["1", "-1"]})
    result = run("numeric_range", {"column": "x", "min": 0}, df)
    assert result.status == CheckStatus.FAIL


def test_numeric_range_skips_non_numeric_text():
    # Documented behavior: 'abc' is not this rule's job. The data_type rule catches it.
    df = pd.DataFrame({"age": ["10", "50", "abc"]})
    result = run("numeric_range", {"column": "age", "min": 0, "max": 120}, df)
    assert result.status == CheckStatus.PASS
    assert result.rows_evaluated == 2


# ---------- 5. allowed_values ----------

def test_allowed_values_pass():
    df = pd.DataFrame({"status": ["Active", "Pending"]})
    config = {"column": "status", "allowed": ["Active", "Inactive", "Pending"]}
    assert run("allowed_values", config, df).status == CheckStatus.PASS


def test_allowed_values_fail_reports_bad_values():
    df = pd.DataFrame({"status": ["Active", "Bogus", "Bogus"]})
    config = {"column": "status", "allowed": ["Active", "Inactive", "Pending"]}
    result = run("allowed_values", config, df)
    assert result.status == CheckStatus.FAIL
    assert result.failed_row_count == 2
    assert result.details["bad_values"] == ["Bogus"]


def test_allowed_values_case_insensitive_option():
    df = pd.DataFrame({"status": ["active"]})
    config = {"column": "status", "allowed": ["ACTIVE"], "case_sensitive": False}
    assert run("allowed_values", config, df).status == CheckStatus.PASS


# ---------- 6. data_type ----------

def test_data_type_integer_fail():
    df = pd.DataFrame({"n": ["1", "2.5", "abc", None]})
    result = run("data_type", {"column": "n", "data_type": "integer"}, df)
    assert result.status == CheckStatus.FAIL
    assert result.rows_evaluated == 3        # the missing value is not evaluated
    assert result.failed_row_count == 2


def test_data_type_integer_pass():
    df = pd.DataFrame({"n": ["1", "2", "-3"]})
    assert run("data_type", {"column": "n", "data_type": "integer"}, df).status == CheckStatus.PASS


def test_data_type_float_pass_and_infinity_fails():
    ok = pd.DataFrame({"n": ["1.5", "2"]})
    bad = pd.DataFrame({"n": ["1.5", "inf"]})
    assert run("data_type", {"column": "n", "data_type": "float"}, ok).status == CheckStatus.PASS
    assert run("data_type", {"column": "n", "data_type": "float"}, bad).status == CheckStatus.FAIL


def test_data_type_date_fails_on_impossible_date():
    df = pd.DataFrame({"d": ["2025-01-01", "2025-02-30", "not-a-date"]})
    result = run("data_type", {"column": "d", "data_type": "date"}, df)
    assert result.status == CheckStatus.FAIL
    assert result.failed_row_count == 2


# ---------- Invalid configuration is rejected when the rule is built ----------

@pytest.mark.parametrize(
    "rule_type, config",
    [
        ("no_such_rule", {}),
        ("required_columns", {}),
        ("required_columns", {"columns": []}),
        ("required_values", {"columns": "id"}),
        ("duplicates", {"columns": []}),
        ("numeric_range", {"column": "age"}),                          # no limits
        ("numeric_range", {"column": "age", "min": 10, "max": 1}),     # min > max
        ("numeric_range", {"column": "age", "min": True}),             # bool is not a number
        ("numeric_range", {"column": "age", "min": float("nan")}),
        ("numeric_range", {"min": 0}),                                 # no column
        ("allowed_values", {"column": "s", "allowed": []}),
        ("allowed_values", {"allowed": ["a"]}),                        # no column
        ("data_type", {"column": "n", "data_type": "banana"}),
        ("data_type", {"data_type": "integer"}),                       # no column
    ],
)
def test_invalid_config_raises_configuration_error(rule_type, config):
    with pytest.raises(ConfigurationError):
        build_rule(rule_type, "bad", config)


def test_invalid_severity_raises_configuration_error():
    with pytest.raises(ConfigurationError):
        build_rule("required_values", "r", {"columns": ["id"]}, severity="CRITICAL")


# ---------- Config problems that only appear at run time ----------

@pytest.mark.parametrize(
    "rule_type, config",
    [
        ("required_values", {"columns": ["ghost"]}),
        ("duplicates", {"columns": ["ghost"]}),
        ("numeric_range", {"column": "ghost", "min": 0}),
        ("allowed_values", {"column": "ghost", "allowed": ["a"]}),
        ("data_type", {"column": "ghost", "data_type": "integer"}),
    ],
)
def test_missing_data_column_is_a_visible_configuration_failure(rule_type, config):
    df = pd.DataFrame({"id": ["1"]})
    result = run(rule_type, config, df)
    assert result.status == CheckStatus.FAIL
    assert result.message.startswith("Configuration error:")
    assert result.details["error"] == "configuration"


# ---------- Engine ----------

def test_rules_do_not_modify_the_dataframe():
    df = pd.DataFrame({"id": ["1", None], "age": ["5", "abc"]})
    before = df.copy()
    rules = [
        build_rule("required_values", "a", {"columns": ["id"]}),
        build_rule("numeric_range", "b", {"column": "age", "min": 0}),
        build_rule("data_type", "c", {"column": "age", "data_type": "integer"}),
        build_rule("duplicates", "d", {}),
    ]
    run_rules(df, rules)
    assert df.equals(before)


def test_engine_returns_one_result_per_rule_and_summarizes():
    df = pd.DataFrame({"id": ["1", None]})
    rules = [
        build_rule("required_columns", "has_id", {"columns": ["id"]}),
        build_rule("required_values", "id_filled", {"columns": ["id"]}),
    ]
    results = run_rules(df, rules)
    assert [r.rule_name for r in results] == ["has_id", "id_filled"]
    assert summarize(results) == {"PASS": 1, "FAIL": 1}


def test_a_crashing_rule_becomes_a_fail_not_an_exception():
    rule = build_rule("required_values", "boom", {"columns": ["id"]})
    rule.evaluate = lambda df: 1 / 0
    results = run_rules(pd.DataFrame({"id": ["1"]}), [rule])
    assert results[0].status == CheckStatus.FAIL
    assert "unexpectedly" in results[0].message
    assert results[0].rule_name == "boom"