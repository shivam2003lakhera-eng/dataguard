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


def _safe_filename(filename: str) -> str:
    """Keep only the final name part, so no folder path is ever exposed."""
    return PureWindowsPath(filename.replace("/", "\\")).name


def read_csv_bytes(
    content: bytes, filename: str, max_bytes: int | None = None
) -> pd.DataFrame:
    """Validate uploaded CSV bytes and return a DataFrame of strings.

    Everything happens in memory. Nothing is written to disk.
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

    if not content.strip():
        raise InvalidSourceDataError("The file is empty.", details)

    try:
        df = pd.read_csv(io.BytesIO(content), dtype=str)
    except UnicodeDecodeError as exc:
        raise InvalidSourceDataError(
            "The file is not valid UTF-8. Re-save it as 'CSV UTF-8'.", details
        ) from exc
    except EmptyDataError as exc:
        raise InvalidSourceDataError("The file has no usable columns.", details) from exc
    except ParserError as exc:
        raise InvalidSourceDataError("The file is not a well-formed CSV.", details) from exc

    if len(df.columns) == 0:
        raise InvalidSourceDataError("The file has no usable columns.", details)

    blank = [c for c in df.columns if str(c).strip() == "" or str(c).startswith("Unnamed:")]
    if blank:
        raise InvalidSourceDataError("The header contains blank column names.", details)

        # pandas renames duplicate headers (a, a -> a, a.1), so check the raw first row.
    raw_header = pd.read_csv(io.BytesIO(content), header=None, nrows=1, dtype=str)
    raw_names = [str(v).strip() for v in raw_header.iloc[0] if pd.notna(v)]
    if len(raw_names) != len(set(raw_names)):
        raise InvalidSourceDataError("The header contains duplicate column names.", details)
    if len(df) == 0:
        raise InvalidSourceDataError("The file has a header but no data rows.", details)

    return df
