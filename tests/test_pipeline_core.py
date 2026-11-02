import json
from pathlib import Path

import pandas as pd
import pytest

from app.core.exceptions import ConfigurationError
from app.processing import runner
from app.processing.runner import build_rules, process_dataframe, run_pipeline
from app.quality.rules.registry import build_rule

SAMPLES = Path(__file__).resolve().parent.parent / "sample_data"
BAD_INSURANCE = SAMPLES / "insurance" / "policies_bad.csv"
CLEAN_INSURANCE = SAMPLES / "insurance" / "policies_clean.csv"
BAD_WEATHER = SAMPLES / "weather" / "weather_bad.csv"

INSURANCE_RULES = [
    {"name": "Required columns exist", "rule_type": "required_columns", "severity": "HIGH",
     "configuration": {"columns": ["policy_id", "premium", "policy_status", "start_date", "end_date"]}},
    {"name": "Policy id is filled", "rule_type": "required_values", "severity": "HIGH",
     "configuration": {"columns": ["policy_id"]}},
    {"name": "Policy id is unique", "rule_type": "duplicates", "severity": "HIGH",
     "configuration": {"columns": ["policy_id"]}},
    {"name": "Premium is not negative", "rule_type": "numeric_range", "severity": "MEDIUM",
     "configuration": {"column": "premium", "min": 0}},
    {"name": "Premium is a number", "rule_type": "data_type", "severity": "MEDIUM",
     "configuration": {"column": "premium", "data_type": "float"}},
    {"name": "Start date is a date", "rule_type": "data_type", "severity": "LOW",
     "configuration": {"column": "start_date", "data_type": "date"}},
    {"name": "End date is a date", "rule_type": "data_type", "severity": "LOW",
     "configuration": {"column": "end_date", "data_type": "date"}},
    {"name": "Status is allowed", "rule_type": "allowed_values", "severity": "LOW",
     "configuration": {"column": "policy_status", "allowed": ["ACTIVE", "EXPIRED", "PENDING"]}},
]

WEATHER_RULES = [
    {"name": "City is filled", "rule_type": "required_values", "configuration": {"columns": ["city"]}},
    {"name": "Time is filled", "rule_type": "required_values", "configuration": {"columns": ["observation_time"]}},
    {"name": "No duplicate rows", "rule_type": "duplicates", "configuration": {}},
    {"name": "Humidity 0 to 100", "rule_type": "numeric_range", "configuration": {"column": "humidity", "min": 0, "max": 100}},
    {"name": "Wind not negative", "rule_type": "numeric_range", "configuration": {"column": "wind_speed", "min": 0}},
]


def process(df, specs, **kwargs):
    return process_dataframe(df, build_rules(specs), **kwargs)


# ---------- Row accounting on the real sample files ----------

def test_insurance_sample_numbers():
    report = run_pipeline(BAD_INSURANCE, INSURANCE_RULES)
    assert report.status == "COMPLETED_WITH_ISSUES"
    assert report.source_rows == 8 and report.source_columns == 5
    # rejected rows: -850 (2), blank id (3), UNKNOWN (4), 'abc' (6), duplicate P2006 (7), not-a-date (8)
    assert [r.data_row for r in report.rejected_sample] == [2, 3, 4, 6, 7, 8]
    assert report.rejected_rows == 6 and report.valid_rows == 2
    assert report.overlap_rows == 0
    assert (report.rules_executed, report.rules_passed, report.rules_failed) == (8, 2, 6)
    assert (report.schema_failures, report.quality_failures) == (0, 6)
    assert report.loadable is True


@pytest.mark.parametrize(
    "path, specs",
    [(BAD_INSURANCE, INSURANCE_RULES), (BAD_WEATHER, WEATHER_RULES)],
)
def test_counts_are_internally_consistent(path, specs):
    r = run_pipeline(path, specs)
    assert r.valid_rows + r.rejected_rows == r.source_rows
    assert r.rules_passed + r.rules_failed == r.rules_executed
    assert r.schema_failures + r.quality_failures == r.rules_failed
    assert r.overlap_rows >= 0
    assert sum(rule.rows_rejected for rule in r.rules) - r.rejected_rows == r.overlap_rows
    assert len(r.rules) == r.rules_executed


def test_weather_sample_duplicate_is_rejected_once():
    r = run_pipeline(BAD_WEATHER, WEATHER_RULES)
    assert r.duplicate_rows == 1
    duplicate_rule = next(rule for rule in r.rules if rule.rule_type == "duplicates")
    assert duplicate_rule.rows_failed == 2      # both rows have an identical twin
    assert duplicate_rule.rows_rejected == 1    # only the extra copy is rejected


def test_overlapping_failures_count_each_row_once():
    df = pd.DataFrame({"id": ["1", "", "3"], "amount": ["5", "-1", "-2"]})
    report = process(df, [
        {"name": "id required", "rule_type": "required_values", "configuration": {"columns": ["id"]}},
        {"name": "amount >= 0", "rule_type": "numeric_range", "configuration": {"column": "amount", "min": 0}},
    ])
    assert report.rejected_rows == 2            # rows 1 and 2
    assert report.valid_rows == 1
    assert report.overlap_rows == 1             # row 1 failed both rules
    assert [rule.rows_rejected for rule in report.rules] == [1, 2]


def test_duplicates_reject_extra_copies_only():
    df = pd.DataFrame({"a": ["x", "x", "x", "y"]})
    report = process(df, [{"name": "unique", "rule_type": "duplicates", "configuration": {}}])
    assert report.rejected_rows == 2 and report.valid_rows == 2
    assert report.rules[0].rows_failed == 3 and report.rules[0].rows_rejected == 2
    assert [row.row_index for row in report.rejected_sample] == [1, 2]  # the first copy is kept


def test_clean_sample_is_success():
    report = run_pipeline(CLEAN_INSURANCE, INSURANCE_RULES[:2])
    assert report.status == "SUCCESS"
    assert report.rejected_rows == 0 and report.valid_rows == report.source_rows
    assert report.loadable is True and report.rejected_sample == []


def test_no_rules_is_success_with_zero_rules():
    report = run_pipeline(CLEAN_INSURANCE, [])
    assert report.status == "SUCCESS"
    assert report.rules_executed == 0 and report.rejected_rows == 0
    assert report.profile["row_count"] == report.source_rows


# ---------- Schema failures are not data quality failures ----------

def test_schema_failures_do_not_reject_rows():
    df = pd.DataFrame({"id": ["1", "2"]})
    report = process(df, [
        {"name": "has email", "rule_type": "required_columns", "configuration": {"columns": ["id", "email"]}},
        {"name": "email filled", "rule_type": "required_values", "configuration": {"columns": ["email"]}},
    ])
    assert report.status == "COMPLETED_WITH_ISSUES"
    assert report.schema_failures == 2 and report.quality_failures == 0
    assert report.rejected_rows == 0 and report.valid_rows == 2
    assert report.loadable is False
    assert {rule.category for rule in report.rules} == {"schema"}


def test_unexpected_columns_can_be_forbidden():
    df = pd.DataFrame({"id": ["1"], "name": ["Asha"]})
    strict = build_rule("required_columns", "r", {"columns": ["id"], "allow_extra": False}).evaluate(df)
    assert strict.status.value == "FAIL"
    assert strict.details["unexpected_columns"] == ["name"]
    assert strict.failed_row_count == 1 and strict.category == "schema"
    assert "Unexpected column(s): name" in strict.message


def test_unexpected_columns_are_allowed_by_default():
    df = pd.DataFrame({"id": ["1"], "name": ["Asha"]})
    assert build_rule("required_columns", "r", {"columns": ["id"]}).evaluate(df).status.value == "PASS"


def test_missing_and_unexpected_columns_are_both_reported():
    df = pd.DataFrame({"name": ["Asha"]})
    result = build_rule("required_columns", "r", {"columns": ["id"], "allow_extra": False}).evaluate(df)
    assert result.failed_row_count == 2
    assert "Missing required column(s): id." in result.message
    assert "Unexpected column(s): name." in result.message


def test_allow_extra_must_be_a_boolean():
    with pytest.raises(ConfigurationError):
        build_rule("required_columns", "r", {"columns": ["id"], "allow_extra": "no"})


# ---------- Explaining each rejected row ----------

def test_rejected_rows_explain_themselves():
    report = run_pipeline(BAD_INSURANCE, INSURANCE_RULES)
    for row in report.rejected_sample:
        assert row.data_row == row.row_index + 1
        assert row.rule and row.rule_type and row.reason and row.columns
    assert "Asha" not in json.dumps(report.to_dict())


def test_rejected_sample_is_capped_and_flags_truncation():
    df = pd.DataFrame({"n": ["-1"] * 50})
    spec = [{"name": "positive", "rule_type": "numeric_range", "configuration": {"column": "n", "min": 0}}]
    capped = process(df, spec, max_rejected_listed=10)
    assert len(capped.rejected_sample) == 10 and capped.rejected_sample_truncated is True
    assert capped.rejected_rows == 50           # the count is exact even when the list is capped
    full = process(df, spec, max_rejected_listed=100)
    assert len(full.rejected_sample) == 50 and full.rejected_sample_truncated is False


# ---------- Failures are reported, never hidden, never "success" ----------

def test_invalid_rule_configuration_is_a_failed_run_with_a_config_error(tmp_path):
    bad = [{"name": "bad", "rule_type": "numeric_range", "configuration": {"column": "premium"}}]
    report = run_pipeline(BAD_INSURANCE, bad)
    assert report.status == "FAILED"
    assert report.error["code"] == "invalid_configuration"
    assert report.source_rows is None and report.rejected_rows is None and report.valid_rows is None
    assert report.rules_failed == 0  # not a misleading data quality failure


@pytest.mark.parametrize("specs", ["not a list", [42], [{"rule_type": "duplicates"}], [{"name": " ", "rule_type": "duplicates"}]])
def test_malformed_rule_lists_raise_configuration_errors(specs):
    with pytest.raises(ConfigurationError):
        build_rules(specs)


def test_missing_file_is_failed_and_leaks_no_path(tmp_path):
    report = run_pipeline(tmp_path / "nope.csv", [])
    assert report.status == "FAILED"
    assert report.error["code"] == "source_file_not_found"
    assert str(tmp_path) not in json.dumps(report.to_dict())
    assert report.source_file == "nope.csv"


def test_empty_file_is_failed(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_bytes(b"")
    report = run_pipeline(path, [])
    assert report.status == "FAILED" and report.error["code"] == "invalid_source_data"
    assert report.source_rows is None


def test_non_csv_is_failed(tmp_path):
    path = tmp_path / "data.json"
    path.write_text("{}")
    assert run_pipeline(path, []).error["code"] == "unsupported_format"


def test_oversized_file_is_refused_before_reading(tmp_path):
    path = tmp_path / "big.csv"
    path.write_bytes(b"a,b\n1,2\n" * 10)
    report = run_pipeline(path, [], max_bytes=20)
    assert report.status == "FAILED" and report.error["code"] == "file_too_large"


def test_malformed_csv_is_failed_with_line_information(tmp_path):
    path = tmp_path / "ragged.csv"
    path.write_text("a,b,c\n1,2\n3,4,5\n")
    report = run_pipeline(path, [])
    assert report.status == "FAILED" and report.error["code"] == "invalid_source_data"
    assert "line 2" in report.error["message"]


def test_unexpected_crash_is_failed_not_success_and_hides_details(tmp_path, monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("secret detail " + str(tmp_path))

    monkeypatch.setattr(runner, "process_dataframe", explode)
    report = run_pipeline(CLEAN_INSURANCE, [])
    assert report.status == "FAILED"
    assert report.error["code"] == "internal_error"
    assert "secret" not in json.dumps(report.to_dict())
    assert str(tmp_path) not in json.dumps(report.to_dict())


def test_a_crashing_rule_is_a_failed_check_not_a_success():
    df = pd.DataFrame({"id": ["1"]})
    rule = build_rule("required_values", "boom", {"columns": ["id"]})
    rule.evaluate = lambda frame: 1 / 0
    report = process_dataframe(df, [rule])
    assert report.status == "COMPLETED_WITH_ISSUES"
    assert report.rules_failed == 1 and report.rules_crashed == 1
    assert report.rejected_rows == 0


# ---------- Report hygiene ----------

def test_report_is_json_safe_and_complete():
    report = run_pipeline(BAD_WEATHER, WEATHER_RULES)
    data = json.loads(json.dumps(report.to_dict(), allow_nan=False))
    for key in ("run_id", "status", "source_rows", "valid_rows", "rejected_rows", "duplicate_rows",
                "rules_executed", "rules_passed", "rules_failed", "duration_ms", "timings_ms", "rules"):
        assert key in data


def test_timings_are_measured():
    report = run_pipeline(BAD_WEATHER, WEATHER_RULES)
    assert set(report.timings_ms) >= {"extract", "profile", "validate"}
    assert all(value >= 0 for value in report.timings_ms.values())
    assert report.duration_ms >= report.timings_ms["extract"]


def test_run_ids_are_unique():
    ids = {run_pipeline(CLEAN_INSURANCE, []).run_id for _ in range(5)}
    assert len(ids) == 5


def test_processing_does_not_modify_the_dataframe():
    df = pd.DataFrame({"id": ["1", "", "1"], "amount": ["5", "-1", "abc"]})
    before = df.copy()
    process(df, [
        {"name": "id", "rule_type": "required_values", "configuration": {"columns": ["id"]}},
        {"name": "range", "rule_type": "numeric_range", "configuration": {"column": "amount", "min": 0}},
        {"name": "dupes", "rule_type": "duplicates", "configuration": {}},
    ])
    assert df.equals(before)
