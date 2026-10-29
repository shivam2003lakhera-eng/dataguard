# Data policies

How DataGuard treats your data. Each rule below is covered by a test.

## Files that are accepted

- `.csv`, UTF-8 (a BOM is fine), comma-separated, within `MAX_FILE_SIZE_MB`.
- Every row must have the same number of fields as the header. A short row would otherwise be padded with missing values, and rows that all have an extra field would be shifted by pandas, so such files are rejected with the line number.
- A single-column header containing `;`, a tab or `|` is rejected: the file almost certainly uses another delimiter.
- Header names are trimmed of surrounding whitespace (case is kept). Blank or duplicate header names are rejected. A column may be called `Unnamed: 0`.

## Missing values

A cell is missing if it is empty or contains only whitespace. This is one function (`app/core/missing.py`) used by the profile and by every rule, so they cannot disagree.

The text `NA`, `None`, `null`, `N/A` and `NaN` is **data**, not missing. `NA` is a real country code, for example. In a numeric column, a cell such as `NaN` is reported as an invalid value instead of being hidden.

## Types in the profile

- `numeric`: every non-missing value is a finite number (`inf` is not).
- `date`: every non-missing value is ISO (`2025-01-31` or `2025-01-31T10:00:00`). Values with a time zone such as `Z` or `+05:30` are not recognised and make the column `text`.
- `mixed`: some values are numbers, some are not. Min, max and mean use the numbers only.
- `text` and `empty`.
- Identifiers such as `00123` are numeric by this rule.

## Duplicates

Three different numbers, always labelled:

| Name | Meaning |
|---|---|
| `duplicate_row_count` | extra copies beyond the first of each group |
| `rows_in_duplicate_groups` | every row that has an identical twin |
| `duplicate_group_count` | how many different rows repeat |

The profile compares whole rows. The `duplicates` rule can use key columns instead, and rows with a missing key are not treated as duplicates.

## What is stored

- CSV rows are processed in memory and never stored.
- Stored: dataset metadata, the profile (counts and min/max), rules, run results and failing **row positions** (at most 5 per rule).
- Raw cell values are **not** stored by default. Set `STORE_SAMPLE_VALUES=true` to also keep up to 5 offending values per rule, which can help debugging but copies data into the database.
- Profile minimum and maximum values for numeric and date columns are stored.