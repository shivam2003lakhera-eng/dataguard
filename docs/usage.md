# Usage

## Account

Open the app and choose **Create one** on the login screen. Enter an email and a password of 8 to 128 characters. Logging out ends the session on the server.

## Upload

Choose **Upload**, enter a name, pick a CSV, and optionally paste rules as JSON and enter key columns:

```json
[{"name":"id required","rule_type":"required_values","configuration":{"columns":["policy_id"]},"severity":"HIGH"}]
```

You land on the quality report. Ready-made rule files are in `sample_data/insurance/policies_bad.rules.json` and `sample_data/weather/weather_bad.rules.json`.

**Key columns** are optional. Leave them empty and no row is ever stored: only the report is. Enter one or more column names (for example `policy_id`) and the valid rows are loaded into the database, so a later file updates the same records. See [data_loading.md](data_loading.md).

## Rule types and configuration

| rule_type | kind | configuration |
|---|---|---|
| `required_columns` | schema | `{"columns": ["a", "b"]}`, plus optional `"allow_extra": false` to also fail on unexpected columns |
| `required_values` | quality | `{"columns": ["a"]}` |
| `duplicates` | quality | `{}` for whole rows, or `{"columns": ["id"]}` |
| `numeric_range` | quality | `{"column": "age", "min": 0, "max": 120}` (min or max may be omitted, not both) |
| `allowed_values` | quality | `{"column": "status", "allowed": ["Active"], "case_sensitive": true}` |
| `data_type` | quality | `{"column": "n", "data_type": "integer"}` (also `float`, `date`) |

A **schema** result judges the shape of the file and never rejects rows. A **quality** result judges the values, and the rows it fails are rejected. A rule that points at a column that does not exist is reported as a schema failure ("Configuration error: ...").

Rules can also be created in the **Manage rules** screen. Invalid configuration is rejected with a clear message.

## The report

- **Checks passed and failed:** how many rules passed.
- **Rows read, valid and rejected:** a row failing several rules is counted once. `valid + rejected = rows read`.
- **Kind:** schema or quality, per rule. **Rejected rows:** how many rows each rule rejects.
- **Not loadable:** shown when a schema check failed.
- **Loading counts** (only for datasets with key columns): records inserted, updated, unchanged and skipped.
- Runs recorded before these numbers existed show `n/a` instead of a made-up zero.

## Running again and history

Open a dataset, then **Run history**, and upload a CSV. It is checked against the dataset's enabled rules. **My runs** in the top bar lists every run of every dataset you own, newest first, with a status filter.

**Input strategy:** DataGuard does not keep the uploaded file, so `POST /datasets/{dataset_id}/runs` always needs a newly uploaded file.

## Command line

```powershell
python -m app.cli run data.csv --rules rules.json
```

No database or web server is needed. See [pipeline.md](pipeline.md).

## API

Interactive docs are at `/docs`. Every endpoint below is under `/api/v1`. All of them need a login cookie except `GET /health`, `POST /auth/register` and `POST /auth/login`.

| Endpoint | Purpose |
|---|---|
| `GET /health` | Health check (public) |
| `POST /auth/register` | Create an account and log in |
| `POST /auth/login` | Log in (5 failed attempts per IP and email in 15 minutes returns 429) |
| `POST /auth/logout` | Log out |
| `GET /auth/me` | The logged-in user |
| `POST /datasets/upload` | Upload a CSV with optional `rules` (JSON) and `key_columns` (comma-separated) |
| `GET /datasets` | My datasets, paginated |
| `GET /datasets/{dataset_id}` | One dataset |
| `PATCH /datasets/{dataset_id}` | Set key columns to turn loading on, or `null` to turn it off |
| `GET /datasets/{dataset_id}/profile` | The latest profile |
| `GET /datasets/{dataset_id}/records` | The rows loaded for this dataset, paginated |
| `DELETE /datasets/{dataset_id}/records` | Remove every loaded row of this dataset |
| `GET /datasets/{dataset_id}/rules` | Rules of a dataset |
| `POST /datasets/{dataset_id}/rules` | Create a rule |
| `PATCH /rules/{rule_id}` | Change a rule's name, configuration, severity or enabled flag |
| `DELETE /rules/{rule_id}` | Delete a rule (past results are kept) |
| `POST /datasets/{dataset_id}/runs` | Check a newly uploaded file against the dataset's rules |
| `GET /datasets/{dataset_id}/runs` | Runs of one dataset, paginated |
| `GET /runs` | All my runs, newest first, with `?status=` |
| `GET /runs/{run_id}` | One run with its results |

Every error has the form `{"error": {"code", "message", "details"}}`. Another user's data always looks like it does not exist (404).

## Notes on behavior

- A numeric range ignores text such as `abc`; use a `data_type` rule to catch it.
- Only empty or whitespace-only cells are missing. "NA", "None" and "null" are treated as data.
- Dates are recognised only in strict ISO form (no time zone designators).
- Uploads over `MAX_FILE_SIZE_MB` (default 50) are rejected.
- Files must be comma-separated UTF-8, with the same number of fields in every row.

The full list is in [data_policies.md](data_policies.md).

## Demo workflow

1. Register an account and log in.
2. Upload `sample_data/insurance/policies_bad.csv`. Paste `sample_data/insurance/policies_bad.rules.json` into the rules box and enter `policy_id` as the key column.
3. Read the report: 8 rows read, 2 valid, 6 rejected, and 2 records inserted.
4. Open **Run history**, upload the same file again, and see 2 records **unchanged**: nothing was written.
5. Open `/docs`, run `GET /datasets/{dataset_id}/records` and see the two loaded rows.
6. Check the Dashboard and **My runs**.
