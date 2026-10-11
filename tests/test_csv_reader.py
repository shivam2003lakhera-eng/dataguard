import pytest

from app.core.exceptions import (
    FileTooLargeError,
    InvalidSourceDataError,
    UnsupportedFormatError,
)
from app.ingestion.csv_reader import read_csv_bytes


def test_valid_csv_is_read_as_strings():
    df = read_csv_bytes(b"id,name\n1,Asha\n2,Ravi\n", "people.csv")

    assert list(df.columns) == ["id", "name"]
    assert len(df) == 2
    assert df["id"].tolist() == ["1", "2"]


def test_utf8_bom_is_handled():
    df = read_csv_bytes(b"\xef\xbb\xbfid,name\n1,x\n", "bom.csv")

    assert list(df.columns) == ["id", "name"]


def test_non_csv_extension_is_rejected():
    with pytest.raises(UnsupportedFormatError):
        read_csv_bytes(b"a,b\n1,2\n", "data.json")


def test_empty_file_is_rejected():
    with pytest.raises(InvalidSourceDataError):
        read_csv_bytes(b"", "empty.csv")


def test_whitespace_only_file_is_rejected():
    with pytest.raises(InvalidSourceDataError):
        read_csv_bytes(b"   \n\n", "blank.csv")


def test_header_only_file_is_rejected():
    with pytest.raises(InvalidSourceDataError):
        read_csv_bytes(b"a,b\n", "header_only.csv")


def test_blank_column_name_is_rejected():
    with pytest.raises(InvalidSourceDataError):
        read_csv_bytes(b"a,,c\n1,2,3\n", "blank_header.csv")


def test_duplicate_column_names_are_rejected():
    with pytest.raises(InvalidSourceDataError):
        read_csv_bytes(b"a,a\n1,2\n", "dupes.csv")


def test_non_utf8_file_gives_friendly_error():
    content = "id,name\n1,caf\xe9\n".encode("cp1252")

    with pytest.raises(InvalidSourceDataError) as exc:
        read_csv_bytes(content, "excel.csv")

    assert "UTF-8" in exc.value.message


def test_oversized_file_is_rejected():
    with pytest.raises(FileTooLargeError):
        read_csv_bytes(b"a,b\n1,2\n", "big.csv", max_bytes=5)


def test_error_details_never_contain_a_server_path():
    with pytest.raises(InvalidSourceDataError) as exc:
        read_csv_bytes(b"", r"C:\secret\folder\empty.csv")

    assert "secret" not in str(exc.value.details)
    assert exc.value.details["filename"] == "empty.csv"