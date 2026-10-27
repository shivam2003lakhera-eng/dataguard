import pandas as pd

from app.profiling.statistics import profile_column


def profile_dataframe(df: pd.DataFrame) -> dict:
    """Describe a whole table as a plain dictionary.

    Duplicates compare whole rows (missing cells compare equal):
      duplicate_row_count       extra copies beyond the first of each group
      rows_in_duplicate_groups  every row that has at least one identical twin
      duplicate_group_count     how many different rows are repeated
    """
    extra_copies = df.duplicated()
    in_groups = df.duplicated(keep=False)
    return {
        "row_count": len(df),
        "column_count": len(df.columns),
        "duplicate_row_count": int(extra_copies.sum()),
        "rows_in_duplicate_groups": int(in_groups.sum()),
        "duplicate_group_count": int(in_groups.sum() - extra_copies.sum()),
        "columns": [profile_column(str(name), df[name]) for name in df.columns],
    }