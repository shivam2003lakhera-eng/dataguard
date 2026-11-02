import contextlib
import io
import json
from pathlib import Path

from app.cli import main

SAMPLES = Path(__file__).resolve().parent.parent / "sample_data"
BAD = str(SAMPLES / "insurance" / "policies_bad.csv")
CLEAN = str(SAMPLES / "insurance" / "policies_clean.csv")

RULES = [
    {"name": "id required", "rule_type": "required_values", "severity": "HIGH",
     "configuration": {"columns": ["policy_id"]}},
]


def run_cli(*argv):
    """Run the CLI and return (exit_code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def rules_file(tmp_path, data=RULES) -> str:
    path = tmp_path / "rules.json"
    path.write_text(json.dumps(data))
    return str(path)


def test_exit_code_1_when_checks_fail(tmp_path):
    code, out, _ = run_cli("run", BAD, "--rules", rules_file(tmp_path))
    assert code == 1
    assert "COMPLETED_WITH_ISSUES" in out
    assert "1 rejected" in out
    assert "data row 3: id required" in out


def test_exit_code_0_when_everything_passes(tmp_path):
    code, out, _ = run_cli("run", CLEAN, "--rules", rules_file(tmp_path))
    assert code == 0 and "SUCCESS" in out


def test_runs_without_a_rules_file():
    code, out, _ = run_cli("run", CLEAN)
    assert code == 0 and "0 run" in out


def test_exit_code_2_for_a_missing_data_file(tmp_path):
    code, out, err = run_cli("run", str(tmp_path / "nope.csv"))
    assert code == 2
    assert "source_file_not_found" in out
    assert str(tmp_path) not in out + err
    assert "Traceback" not in out + err


def test_exit_code_2_for_invalid_rule_configuration(tmp_path):
    bad = [{"name": "x", "rule_type": "numeric_range", "configuration": {"column": "premium"}}]
    code, out, _ = run_cli("run", BAD, "--rules", rules_file(tmp_path, bad))
    assert code == 2 and "invalid_configuration" in out


def test_exit_code_2_when_the_rules_file_is_not_json(tmp_path):
    path = tmp_path / "rules.json"
    path.write_text("this is not json")
    code, out, err = run_cli("run", BAD, "--rules", str(path))
    assert code == 2 and "not valid JSON" in err and out == ""


def test_exit_code_2_when_the_rules_file_is_not_a_list(tmp_path):
    code, _, err = run_cli("run", BAD, "--rules", rules_file(tmp_path, {"name": "x"}))
    assert code == 2 and "JSON list" in err


def test_exit_code_2_when_the_rules_file_is_missing(tmp_path):
    code, _, err = run_cli("run", BAD, "--rules", str(tmp_path / "missing.json"))
    assert code == 2 and "could not be read" in err and str(tmp_path) not in err


def test_json_output_is_valid_and_matches_the_exit_code(tmp_path):
    code, out, _ = run_cli("run", BAD, "--rules", rules_file(tmp_path), "--json")
    data = json.loads(out)
    assert code == 1 and data["status"] == "COMPLETED_WITH_ISSUES"
    assert data["rejected_rows"] == 1 and data["valid_rows"] == 7


def test_output_file_receives_the_full_report(tmp_path):
    target = tmp_path / "report.json"
    code, out, _ = run_cli("run", BAD, "--rules", rules_file(tmp_path), "--output", str(target))
    assert code == 1 and "DataGuard pipeline report" in out
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["source_rows"] == 8 and data["rules_executed"] == 1


def test_unwritable_output_path_is_exit_code_2(tmp_path):
    code, _, err = run_cli("run", CLEAN, "--output", str(tmp_path / "no_such_dir" / "r.json"))
    assert code == 2 and "could not be written" in err


def test_show_rejected_limits_the_text_report(tmp_path):
    code, out, _ = run_cli("run", BAD, "--rules", rules_file(tmp_path), "--show-rejected", "0")
    assert code == 1 and "Rejected rows" not in out


def test_the_shipped_insurance_rules_file_works():
    code, out, _ = run_cli(
        "run", BAD, "--rules", str(SAMPLES / "insurance" / "policies_bad.rules.json"), "--json"
    )
    data = json.loads(out)
    assert code == 1
    assert (data["source_rows"], data["valid_rows"], data["rejected_rows"]) == (8, 2, 6)
    assert (data["rules_executed"], data["rules_passed"], data["rules_failed"]) == (8, 2, 6)


def test_the_shipped_weather_rules_file_works():
    weather = str(SAMPLES / "weather" / "weather_bad.csv")
    code, out, _ = run_cli(
        "run", weather, "--rules", str(SAMPLES / "weather" / "weather_bad.rules.json"), "--json"
    )
    data = json.loads(out)
    assert code == 1
    # rejected: humidity 130 (row 2), missing time (3), wind -12.3 (5 and 6; row 6 is also the duplicate)
    assert (data["source_rows"], data["valid_rows"], data["rejected_rows"]) == (7, 3, 4)
    assert data["overlap_rows"] == 1  # the duplicated Mumbai row fails two rules but counts once
