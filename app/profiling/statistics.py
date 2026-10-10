import pandas as pd


def infer_column_type(series: pd.Series) -> str:
    """Guess a column's type: 'empty', 'numeric', 'mixed', or 'text'."""
    values = series.dropna()
    if values.empty:
        return "empty"

    converted = pd.to_numeric(values, errors="coerce")
    numeric_count = int(converted.notna().sum())

    if numeric_count == len(values):
        return "numeric"
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
        numbers = pd.to_numeric(series, errors="coerce").dropna()
        profile["min"] = float(numbers.min())
        profile["max"] = float(numbers.max())
        profile["mean"] = round(float(numbers.mean()), 2)

    return profile