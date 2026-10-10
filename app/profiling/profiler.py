import pandas as pd

from app.profiling.statistics import profile_column


def profile_dataframe(df: pd.DataFrame) -> dict:
    """Describe a whole table as a plain dictionary."""
    return {
        "row_count": len(df),
        "column_count": len(df.columns),
        "duplicate_row_count": int(df.duplicated().sum()),
        "columns": [profile_column(str(name), df[name]) for name in df.columns],
    }