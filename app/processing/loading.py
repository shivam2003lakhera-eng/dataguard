"""Prepare the valid rows of a file for loading. Pure pandas: no database here.

The database side (the upsert itself) lives in app/services/loading.py.

Loading is opt-in: it only happens for a dataset that has key_columns. The key
columns identify a record, so the same record in a later file updates the same
stored row instead of creating a copy.
"""
import json
from collections.abc import Iterator
from dataclasses import dataclass

import pandas as pd

from app.core.exceptions import ConfigurationError
from app.core.missing import is_missing

MAX_KEY_COLUMNS = 20
MAX_KEY_LENGTH = 500   # the row_key column is VARCHAR(500)
CHUNK_SIZE = 1000


def validate_key_columns(names: list[str] | None) -> list[str] | None:
    """Check a list of key column names. None means "do not load"."""
    if names is None:
        return None
    if not isinstance(names, list) or not names:
        raise ConfigurationError("key_columns must be a non-empty list of column names, or null.")
    cleaned = []
    for name in names:
        if not isinstance(name, str) or not name.strip():
            raise ConfigurationError("Every key column name must be non-empty text.")
        cleaned.append(name.strip())
    if len(cleaned) != len(set(cleaned)):
        raise ConfigurationError("key_columns must not repeat a column.")
    if len(cleaned) > MAX_KEY_COLUMNS:
        raise ConfigurationError(f"At most {MAX_KEY_COLUMNS} key columns are allowed.")
    return cleaned


def parse_key_columns(raw: str | None) -> list[str] | None:
    """Turn 'a, b' from a form field into ['a', 'b']. Empty text means None."""
    if raw is None or not raw.strip():
        return None
    return validate_key_columns([part for part in raw.split(",")])


@dataclass
class LoadStats:
    """Valid rows that were not loaded, and why. Filled in while iterating."""

    missing_key: int = 0
    key_too_long: int = 0
    duplicate_key: int = 0

    @property
    def skipped(self) -> int:
        return self.missing_key + self.key_too_long + self.duplicate_key


def make_row_key(values: list[str]) -> str:
    """An unambiguous text key for one or several key values."""
    return json.dumps(values, ensure_ascii=False, separators=(",", ":"))


def iter_records(
    df: pd.DataFrame,
    rejected_index: frozenset[int] | set[int],
    key_columns: list[str],
    stats: LoadStats,
    chunk_size: int = CHUNK_SIZE,
) -> Iterator[list[dict]]:
    """Yield the valid rows as {"row_key", "data"} records, in chunks.

    Rules:
      * Rejected rows are never loaded.
      * A row with a missing key value is skipped (counted in stats.missing_key).
      * If the same key appears twice in the file, the FIRST row wins and the
        later ones are skipped (stats.duplicate_key). This also matches the
        duplicates rule, which keeps the first copy.
      * Missing cells are stored as null. Other values are stored exactly as read
        (text), never converted.
    The DataFrame is only read, never modified.
    """
    valid = df[~df.index.isin(list(rejected_index))]
    columns = list(df.columns)
    seen: set[str] = set()

    for start in range(0, len(valid), chunk_size):
        block = valid.iloc[start:start + chunk_size]
        values = {column: block[column].tolist() for column in columns}
        missing = {column: is_missing(block[column]).tolist() for column in columns}
        chunk = []
        for i in range(len(block)):
            if any(missing[column][i] for column in key_columns):
                stats.missing_key += 1
                continue
            row_key = make_row_key([values[column][i] for column in key_columns])
            if len(row_key) > MAX_KEY_LENGTH:
                stats.key_too_long += 1
                continue
            if row_key in seen:
                stats.duplicate_key += 1
                continue
            seen.add(row_key)
            chunk.append({
                "row_key": row_key,
                "data": {c: (None if missing[c][i] else values[c][i]) for c in columns},
            })
        if chunk:
            yield chunk
