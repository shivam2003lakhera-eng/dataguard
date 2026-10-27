import pandas as pd


def is_missing(series: pd.Series) -> pd.Series:
    """True where a cell is missing.

    The single definition for the whole project: a cell is missing if it is
    NaN/None, empty text, or text containing only whitespace. The profiler and
    every rule use this, so they can never disagree. The input is not modified.
    """
    return series.isna() | series.astype(str).str.strip().eq("")