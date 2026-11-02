# Pipeline, report and command line

The processing core lives in `app/processing/` and has **no dependency on FastAPI or the database**. The web app, the command line and the tests all call the same functions.

```
CSV bytes -> extract -> profile -> validate -> separate valid / rejected rows -> report
```

| Stage | Code | What it does |
|---|---|---|
| Extract | `app/ingestion/csv_reader.py` | Size, encoding, delimiter, header and row-width checks. Rejects bad files with a clear message. |
| Profile | `app/profiling/` | Types, missing values, duplicates, distinct counts, min and max. |
| Validate | `app/quality/` | Runs the six rule types. Each rule says which rows it rejects and why. |
| Report | `app/processing/runner.py` | Counts valid and rejected rows and builds the report. |

## Functions

| Function | Use |
|---|---|
| `run_pipeline(path, rules)` | A CSV file in, a `PipelineReport` out. **Never raises**: every failure comes back as a report with status `FAILED`. |
| `process_dataframe(df, rules)` | The pure core: a DataFrame and built rules in, a report out. The DataFrame is only read. |
| `build_rules(specs)` | Rule dictionaries to validated rules. Raises `ConfigurationError` for a bad configuration, before any data is read. |

## Command line

No database is needed.

```powershell
python -m app.cli run sample_data/insurance/policies_bad.csv --rules sample_data/insurance/policies_bad.rules.json
python -m app.cli run data.csv --rules rules.json --json
python -m app.cli run data.csv --rules rules.json --output report.json
```

| Option | Meaning |
|---|---|
| `--rules FILE` | A JSON list of rules, the same format as the upload form. |
| `--json` | Print the full report as JSON. |
| `--output FILE` | Also write the full JSON report to a file. |
| `--show-rejected N` | Rejected rows printed in the text report (default 10). |
| `--max-rejected N` | Rejected rows kept in the report sample (default 200). |

| Exit code | Meaning |
|---|---|
| 0 | `SUCCESS`: every check passed |
| 1 | `COMPLETED_WITH_ISSUES`: the run finished and at least one check failed |
| 2 | `FAILED`: the run could not complete (bad file, bad rules, unexpected error) |

## Statuses

- `SUCCESS`: every rule passed (including a run with no rules).
- `COMPLETED_WITH_ISSUES`: the run finished and at least one rule failed. **A failed check is not a failed run.**
- `FAILED`: the run could not finish. The report has an `error` with a `code` and a `message`, and every count that was never measured is `null` instead of `0`.

## Counting rules

| Field | Definition |
|---|---|
| `source_rows` | Data rows in the file (the header is not counted). |
| `rejected_rows` | Rows rejected by at least one **quality** rule. A row failing several rules counts once. |
| `valid_rows` | `source_rows - rejected_rows`. |
| `overlap_rows` | The sum of every rule's rejected rows, minus `rejected_rows`. It shows how much the rules overlap. |
| `duplicate_rows` | Extra copies of whole rows (from the profile). |
| `rules_executed` | `rules_passed + rules_failed`. |
| `schema_failures` | Failed schema rules. `schema_failures + quality_failures == rules_failed`. |
| `rules_crashed` | Rules that raised an unexpected error. They count as failed, never as passed. |
| `loadable` | `true` only if no schema rule failed. |

Duplicates: the **first** row of each group is kept and only the **extra copies** are rejected. The rule's own `rows_failed` still counts every row that has an identical twin, so both numbers are visible.

## Schema failures versus quality failures

- **Schema** rules judge the shape of the file: `required_columns`, and any rule that could not run because its column does not exist (reported as "Configuration error: ..."). They never reject rows. They set `loadable` to `false`.
- **Quality** rules judge the values in the rows. They reject rows.

`required_columns` takes an optional `"allow_extra": false` to also fail on columns that are not in the list. The default allows extra columns.

```json
{"name": "Exact columns", "rule_type": "required_columns",
 "configuration": {"columns": ["id", "name"], "allow_extra": false}}
```

## What a rejected row contains

`row_index` (0-based), `data_row` (1-based, the first row after the header is 1), the rule name and type, the column names and a short reason such as "value outside the allowed range". **Cell values are never included.**

## Measured performance

Measured with `python -m scripts.benchmark` in a Linux sandbox: 1 CPU, Python 3.12.3, pandas 3.0.2, seven rules, synthetic customer data with problems planted at known rates. Each size ran once in a fresh process. Treat the numbers as indicative of this machine only.

| rows | file MB | extract s | profile s | validate s | total s | rows/s | peak MB | valid | rejected |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 10,000 | 0.5 | 0.03 | 0.08 | 0.05 | 0.15 | 65,270 | 72.2 | 9,633 | 367 |
| 100,000 | 4.7 | 0.13 | 0.50 | 0.27 | 0.91 | 110,467 | 120.5 | 96,546 | 3,454 |
| 1,000,000 | 47.3 | 1.39 | 6.28 | 2.80 | 10.48 | 95,441 | 595.0 | 965,631 | 34,369 |

- **Memory:** about 72 MB before any data is read. A 47 MB file needs roughly 600 MB in total, about 12 times its size, because pandas holds every cell as a Python string. Keep `MAX_FILE_SIZE_MB` well below your memory limit divided by 12.
- **Profiling is the slowest stage.** A change that skips the date parse when a small sample already proves a column is not a date reduced profiling from 9.0 s to 6.3 s at 1,000,000 rows, with identical results.
- Not measured: Windows, more than one CPU, `pyarrow`-backed strings (install `pyarrow` and re-run the benchmark to see the difference).
- This is not a distributed system. Files are processed in memory on one machine.

Run it yourself and replace the table with your own numbers:

```powershell
python -m scripts.benchmark
```
