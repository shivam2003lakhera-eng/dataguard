import pytest

from app.core.exceptions import InvalidSourceDataError
from app.ingestion.csv_reader import read_csv_bytes


def read(text: str, name: str = "data.csv"):
    return read_csv_bytes(text.encode("utf-8"), name)


# ---------- Missing-value policy: only an empty cell is missing ----------

def test_na_like_text_is_data_not_missing():
    df = read("country,note\nNA,None\nIN,null\nUS,N/A\n")
    assert int(df.isna().sum().sum()) == 0
    assert df["country"].tolist() == ["NA", "IN", "US"]


def test_empty_cell_is_still_missing():
    df = read("id,name\n1,Asha\n2,\n")
    assert df["name"].isna().tolist() == [False, True]


# ---------- Headers ----------

def test_header_whitespace_is_trimmed():
    assert list(read(" id , name \n1,x\n").columns) == ["id", "name"]


def test_headers_that_differ_only_by_whitespace_are_duplicates():
    with pytest.raises(InvalidSourceDataError):
        read("a,a \n1,2\n")


def test_whitespace_only_header_name_is_rejected():
    with pytest.raises(InvalidSourceDataError):
        read("a, ,c\n1,2,3\n")


def test_a_column_literally_named_unnamed_is_allowed():
    assert list(read("Unnamed: 0,x\n0,1\n").columns) == ["Unnamed: 0", "x"]


# ---------- Delimiter ----------

@pytest.mark.parametrize(
    "text, word",
    [
        ("id;name;age\n1;Asha;30\n", "semicolon"),
        ("id\tname\n1\tAsha\n", "tab"),
        ("id|name\n1|Asha\n", "pipe"),
    ],
)
def test_wrong_delimiter_is_rejected_with_advice(text, word):
    with pytest.raises(InvalidSourceDataError) as exc:
        read(text)
    assert word in exc.value.message
    assert "comma" in exc.value.message.lower()


def test_single_column_csv_is_allowed():
    assert list(read("id\n1\n2\n").columns) == ["id"]


# ---------- Rows with the wrong number of fields ----------

def test_row_with_too_few_fields_is_rejected_with_its_line_number():
    with pytest.raises(InvalidSourceDataError) as exc:
        read("a,b,c\n1,2\n3,4,5\n")
    assert exc.value.details["bad_lines"] == [2]
    assert exc.value.details["expected_fields"] == 3


def test_row_with_too_many_fields_is_rejected():
    with pytest.raises(InvalidSourceDataError) as exc:
        read("a,b\n1,2\n3,4,5\n")
    assert exc.value.details["bad_lines"] == [3]


def test_every_row_having_an_extra_field_is_rejected_not_shifted():
    with pytest.raises(InvalidSourceDataError) as exc:
        read("a,b\n1,2,3\n4,5,6\n")
    assert exc.value.details["bad_row_count"] == 2


def test_quoted_newline_is_one_row():
    df = read('a,b\n"line1\nline2",x\n')
    assert len(df) == 1
    assert df.iloc[0, 0] == "line1\nline2"


def test_blank_lines_are_ignored():
    assert len(read("a,b\n1,2\n\n3,4\n")) == 2


def test_structure_errors_never_echo_cell_values():
    with pytest.raises(InvalidSourceDataError) as exc:
        read("id,name\n1,Asha,SECRET\n")
    shown = exc.value.message + str(exc.value.details)
    assert "Asha" not in shown and "SECRET" not in shown