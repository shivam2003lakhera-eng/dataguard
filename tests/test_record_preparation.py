import pandas as pd
import pytest

from app.core.exceptions import ConfigurationError
from app.processing.loading import (
    MAX_KEY_LENGTH,
    LoadStats,
    iter_records,
    make_row_key,
    parse_key_columns,
    validate_key_columns,
)
from app.processing.runner import account_rows
from app.quality.rules.registry import build_rule


def records(df, keys, rejected=(), chunk_size=1000):
    stats = LoadStats()
    chunks = list(iter_records(df, frozenset(rejected), keys, stats, chunk_size))
    return [record for chunk in chunks for record in chunk], stats, chunks


def test_valid_rows_become_records_with_a_key_and_their_data():
    df = pd.DataFrame({"id": ["1", "2"], "name": ["Asha", "Ravi"]})
    found, stats, _ = records(df, ["id"])
    assert found == [
        {"row_key": '["1"]', "data": {"id": "1", "name": "Asha"}},
        {"row_key": '["2"]', "data": {"id": "2", "name": "Ravi"}},
    ]
    assert stats.skipped == 0


def test_rejected_rows_are_never_loaded():
    df = pd.DataFrame({"id": ["1", "2", "3"], "v": list("abc")})
    found, _, _ = records(df, ["id"], rejected={1})
    assert [r["row_key"] for r in found] == ['["1"]', '["3"]']


def test_missing_cells_become_null_and_values_stay_text():
    df = pd.DataFrame({"id": ["1", "2"], "name": ["   ", None], "n": ["007", "1.50"]})
    found, _, _ = records(df, ["id"])
    assert found[0]["data"] == {"id": "1", "name": None, "n": "007"}   # not converted to 7
    assert found[1]["data"] == {"id": "2", "name": None, "n": "1.50"}


def test_rows_with_a_missing_key_are_skipped_and_counted():
    df = pd.DataFrame({"id": ["1", "", None, "  ", "5"], "v": list("abcde")})
    found, stats, _ = records(df, ["id"])
    assert [r["row_key"] for r in found] == ['["1"]', '["5"]']
    assert stats.missing_key == 3 and stats.skipped == 3


def test_duplicate_keys_in_one_file_keep_the_first_row():
    df = pd.DataFrame({"id": ["1", "2", "1", "1"], "v": ["first", "x", "second", "third"]})
    found, stats, _ = records(df, ["id"])
    assert [r["data"]["v"] for r in found] == ["first", "x"]
    assert stats.duplicate_key == 2


def test_duplicate_keys_are_detected_across_chunks():
    df = pd.DataFrame({"id": ["1", "2", "3", "1"], "v": list("abcd")})
    found, stats, chunks = records(df, ["id"], chunk_size=2)
    assert len(chunks) >= 2                       # the file really was split
    assert [r["row_key"] for r in found] == ['["1"]', '["2"]', '["3"]']
    assert stats.duplicate_key == 1


def test_a_composite_key_uses_all_its_columns():
    df = pd.DataFrame({"id": ["1", "1", "1"], "region": ["N", "S", "N"], "v": list("abc")})
    found, stats, _ = records(df, ["id", "region"])
    assert [r["row_key"] for r in found] == ['["1","N"]', '["1","S"]']
    assert found[0]["data"]["v"] == "a" and stats.duplicate_key == 1


def test_keys_are_unambiguous():
    assert make_row_key(["a,b", "c"]) != make_row_key(["a", "b,c"])
    assert make_row_key(["ab", "c"]) != make_row_key(["a", "bc"])


def test_a_key_that_is_too_long_is_skipped():
    df = pd.DataFrame({"id": ["x" * (MAX_KEY_LENGTH + 1), "ok"], "v": ["a", "b"]})
    found, stats, _ = records(df, ["id"])
    assert [r["row_key"] for r in found] == ['["ok"]']
    assert stats.key_too_long == 1


def test_everything_valid_is_accounted_for():
    df = pd.DataFrame({"id": ["1", "", "1", "2", "3"], "v": list("abcde")})
    found, stats, _ = records(df, ["id"], rejected={4})
    valid_rows = len(df) - 1
    assert len(found) + stats.skipped == valid_rows


def test_preparing_records_does_not_modify_the_dataframe():
    df = pd.DataFrame({"id": ["1", "", "1"], "v": ["a", "  ", None]})
    before = df.copy()
    records(df, ["id"], rejected={0})
    assert df.equals(before)


def test_an_empty_result_yields_nothing():
    df = pd.DataFrame({"id": ["1"], "v": ["a"]})
    found, stats, chunks = records(df, ["id"], rejected={0})
    assert found == [] and chunks == [] and stats.skipped == 0


# ---------- key column validation ----------

def test_key_columns_are_trimmed_and_none_means_no_loading():
    assert validate_key_columns(None) is None
    assert validate_key_columns([" id ", "region"]) == ["id", "region"]
    assert parse_key_columns(None) is None
    assert parse_key_columns("   ") is None
    assert parse_key_columns("id, region") == ["id", "region"]


@pytest.mark.parametrize("bad", [[], [""], ["  "], ["id", "id"], ["id", " id "], [1], "id", ["c%d" % i for i in range(21)]])
def test_invalid_key_columns_are_rejected(bad):
    with pytest.raises(ConfigurationError):
        validate_key_columns(bad)


def test_an_empty_name_in_a_form_field_is_rejected():
    with pytest.raises(ConfigurationError):
        parse_key_columns("id,,region")


# ---------- which rows were rejected ----------

def test_account_rows_reports_which_rows_were_rejected():
    from app.quality.engine import run_rules

    df = pd.DataFrame({"id": ["1", "", "3"], "amount": ["5", "-1", "-2"]})
    results = run_rules(df, [
        build_rule("required_values", "id", {"columns": ["id"]}),
        build_rule("numeric_range", "amount", {"column": "amount", "min": 0}),
        build_rule("required_columns", "cols", {"columns": ["id"]}),
    ])
    counts = account_rows(results, len(df))
    assert counts.rejected_index == frozenset({1, 2})
    assert (counts.rejected_rows, counts.valid_rows, counts.overlap_rows) == (2, 1, 1)
