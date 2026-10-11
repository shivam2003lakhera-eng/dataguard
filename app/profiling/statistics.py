import pandas as pd

# ISO 8601 shape: YYYY-MM-DD, optionally followed by T or a space and a time.
ISO_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?)?$"


def to_finite_numbers(series: pd.Series) -> pd.Series:
    """Convert to numbers; anything not a finite number becomes NaN.

    Returns a new Series. The input is never modified.
    """
    numbers = pd.to_numeric(series, errors="coerce")
    return numbers.where(numbers.abs() != float("inf"))


def parse_iso_dates(series: pd.Series) -> pd.Series:
    """Parse strictly ISO-formatted values; anything else becomes NaT."""
    text = series.astype("string").str.strip()
    shaped = text.str.match(ISO_DATE_PATTERN, na=False)
    parsed = pd.to_datetime(text.where(shaped), errors="coerce", format="mixed")
    return parsed


def infer_column_type(series: pd.Series) -> str:
    """Guess a column's type: 'empty', 'numeric', 'date', 'mixed', or 'text'."""
    values = series.dropna()
    if values.empty:
        return "empty"

    numeric_count = int(to_finite_numbers(values).notna().sum())
    if numeric_count == len(values):
        return "numeric"

    date_count = int(parse_iso_dates(values).notna().sum())
    if date_count == len(values):
        return "date"

    if numeric_count == 0:
        return "text"
    return "mixed"


def profile_column(name: str, series: pd.Series) -> dict:
    """Describe one column as a plain dictionary."""
    total = len(series)
    null_count = int(series.isna().sum())
    inferred_type = infer_column_type(series)

    profile = {
        "name": name,
        "inferred_type": inferred_type,
        "non_null_count": total - null_count,
        "null_count": null_count,
        "null_percent": round(null_count / total * 100, 2) if total else 0.0,
        "distinct_count": int(series.nunique()),
        "min": None,
        "max": None,
        "mean": None,
    }

    if inferred_type in ("numeric", "mixed"):
        numbers = to_finite_numbers(series).dropna()
        if not numbers.empty:
            profile["min"] = float(numbers.min())
            profile["max"] = float(numbers.max())
            profile["mean"] = round(float(numbers.mean()), 2)
    elif inferred_type == "date":
        dates = parse_iso_dates(series).dropna()
        profile["min"] = dates.min().date().isoformat() if (dates.dt.time == pd.Timestamp(0).time()).all() else dates.min().isoformat()
        profile["max"] = dates.max().date().isoformat() if (dates.dt.time == pd.Timestamp(0).time()).all() else dates.max().isoformat()

    return profile