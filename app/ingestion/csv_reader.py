import csv
import io
from pathlib import PureWindowsPath

import pandas as pd
from pandas.errors import EmptyDataError, ParserError

from app.core.config import get_settings
from app.core.exceptions import (
    FileTooLargeError,
    InvalidSourceDataError,
    UnsupportedFormatError,
)

SUSPECT_DELIMITERS = {";": "semicolon", "\t": "tab", "|": "pipe"}
MAX_REPORTED_LINES = 5


def _safe_filename(filename: str) -> str:
    """Keep only the final name part, so no folder path is ever exposed."""
    return PureWindowsPath(filename.replace("/", "\\")).name


def _scan_structure(content: bytes, details: dict) -> list[str]:
    """One streaming pass over the file.

    Returns the raw header names, and rejects files whose rows do not all have
    the same number of fields as the header. pandas would pad short rows with
    missing values, and would silently shift the data if every row had an extra
    field, so we check this ourselves.
    """
    bad_count = 0
    bad_lines: list[int] = []
    try:
        reader = csv.reader(io.TextIOWrapper(io.BytesIO(content), encoding="utf-8-sig", newline=""))
        header = next(reader, None)
        if header is None:
            raise InvalidSourceDataError("The file has no usable columns.", details)
        width = len(header)
        for row in reader:
            if row and len(row) != width:  # an empty list is a blank line, which pandas skips too
                bad_count += 1
                if len(bad_lines) < MAX_REPORTED_LINES:
                    bad_lines.append(reader.line_num)
    except UnicodeDecodeError as exc:
        raise InvalidSourceDataError(
            "The file is not valid UTF-8. Re-save it as 'CSV UTF-8'.", details
        ) from exc
    except csv.Error as exc:
        raise InvalidSourceDataError("The file is not a well-formed CSV.", details) from exc

    if width == 1:
        for character, word in SUSPECT_DELIMITERS.items():
            if character in header[0]:
                raise InvalidSourceDataError(
                    f"The file looks {word}-separated. Save it as a comma-separated CSV (CSV UTF-8).",
                    details,
                )

    if bad_count:
        raise InvalidSourceDataError(
            f"{bad_count} row(s) do not have {width} fields like the header. "
            f"First problem at line {bad_lines[0]}.",
            {**details, "expected_fields": width, "bad_row_count": bad_count, "bad_lines": bad_lines},
        )
    return header


def read_csv_bytes(
    content: bytes, filename: str, max_bytes: int | None = None
) -> pd.DataFrame:
    """Validate uploaded CSV bytes and return a DataFrame of strings.

    Everything happens in memory. Nothing is written to disk.
    Only an empty cell counts as missing: "NA", "None" or "null" are data.
    """
    name = _safe_filename(filename)
    details = {"filename": name}

    if not name.lower().endswith(".csv"):
        raise UnsupportedFormatError("Only .csv files are supported.", details)

    if max_bytes is None:
        max_bytes = get_settings().max_file_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise FileTooLargeError(
            "File exceeds the maximum allowed size.",
            {**details, "limit_mb": round(max_bytes / (1024 * 1024), 2)},
        )

    if not content or content.isspace():  # isspace() does not copy the bytes
        raise InvalidSourceDataError("The file is empty.", details)

    names = [raw.strip() for raw in _scan_structure(content, details)]
    if any(column == "" for column in names):
        raise InvalidSourceDataError("The header contains blank column names.", details)
    if len(set(names)) != len(names):
        raise InvalidSourceDataError("The header contains duplicate column names.", details)

    try:
        df = pd.read_csv(
            io.BytesIO(content), dtype=str, keep_default_na=False, na_values=[""]
        )
    except UnicodeDecodeError as exc:
        raise InvalidSourceDataError(
            "The file is not valid UTF-8. Re-save it as 'CSV UTF-8'.", details
        ) from exc
    except EmptyDataError as exc:
        raise InvalidSourceDataError("The file has no usable columns.", details) from exc
    except ParserError as exc:
        raise InvalidSourceDataError("The file is not a well-formed CSV.", details) from exc

    if len(df.columns) != len(names):
        raise InvalidSourceDataError("The file is not a well-formed CSV.", details)
    df.columns = names  # same names, with surrounding whitespace trimmed

    if len(df) == 0:
        raise InvalidSourceDataError("The file has a header but no data rows.", details)

    return df