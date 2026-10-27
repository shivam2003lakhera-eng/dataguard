import pandas as pd

from app.core.missing import is_missing

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
    return pd.to_datetime(text.where(shaped), errors="coerce", format="mixed")


def _analyze(values: pd.Series) -> tuple[str, pd.Series | None]:
    """Classify non-missing values. Returns (type, parsed numbers or dates)."""
    if values.empty:
        return "empty", None

    numbers = to_finite_numbers(values)
    numeric_count = int(numbers.notna().sum())
    if numeric_count == len(values):
        return "numeric", numbers

    dates = parse_iso_dates(values)
    if int(dates.notna().sum()) == len(values):
        return "date", dates

    if numeric_count == 0:
        return "text", None
    return "mixed", numbers


def infer_column_type(series: pd.Series) -> str:
    """Guess a column's type: 'empty', 'numeric', 'date', 'mixed', or 'text'."""
    return _analyze(series[~is_missing(series)])[0]


def profile_column(name: str, series: pd.Series) -> dict:
    """Describe one column as a plain dictionary."""
    missing = is_missing(series)
    values = series[~missing]
    total = len(series)
    null_count = int(missing.sum())
    inferred_type, parsed = _analyze(values)

    profile = {
        "name": name,
        "inferred_type": inferred_type,
        "non_null_count": total - null_count,
        "null_count": null_count,
        "null_percent": round(null_count / total * 100, 2) if total else 0.0,
        "distinct_count": int(values.nunique()),
        "min": None,
        "max": None,
        "mean": None,
    }

    if inferred_type in ("numeric", "mixed"):
        numbers = parsed.dropna()
        if not numbers.empty:
            profile["min"] = float(numbers.min())
            profile["max"] = float(numbers.max())
            profile["mean"] = round(float(numbers.mean()), 2)
    elif inferred_type == "date":
        dates = parsed.dropna()
        date_only = bool((dates.dt.time == pd.Timestamp(0).time()).all())

        def show(stamp):
            return stamp.date().isoformat() if date_only else stamp.isoformat()

        profile["min"] = show(dates.min())
        profile["max"] = show(dates.max())

    return profile