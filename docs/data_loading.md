# Loading valid rows (opt-in)

By default DataGuard stores **no rows**: it validates a file, saves the report, and forgets the data.

If you give a dataset **key columns**, DataGuard also **loads the valid rows** into PostgreSQL, so the dataset becomes a table you can query, and a later file updates the same records instead of duplicating them.

```
CSV -> extract -> profile -> validate -> split valid / rejected -> upsert valid rows -> report
```

## Turning it on

| How | What to do |
|---|---|
| At upload | Fill in "Key column(s)" on the Upload page, or send the form field `key_columns` (comma-separated). |
| Later | `PATCH /api/v1/datasets/{id}` with `{"key_columns": ["id"]}`. It applies to the next run. |
| Turning it off | `PATCH` with `{"key_columns": null}`. Records already loaded are **kept**. |
| Deleting the data | `DELETE /api/v1/datasets/{id}/records` removes every loaded row. The dataset and its history stay. |
| Reading it | `GET /api/v1/datasets/{id}/records?limit=50&offset=0` |

Key columns must exist in the file; otherwise the upload is rejected before anything is saved.

## What is loaded

- Only **valid** rows: a row rejected by any quality rule is never loaded.
- A record is `{row_key, data}`. `row_key` is the key values as JSON text (`["C001"]`, `["1","N"]`), so a composite key cannot be confused with another one. `data` holds every column as text, **exactly as read**: `007` stays `007`.
- A missing cell (empty or only spaces) is stored as `null`.

## Idempotency

The load is one SQL statement per chunk of 1,000 rows:

```sql
INSERT INTO dataset_records (dataset_id, row_key, data) VALUES (...)
ON CONFLICT (dataset_id, row_key)
DO UPDATE SET data = EXCLUDED.data, updated_at = now()
WHERE dataset_records.data IS DISTINCT FROM EXCLUDED.data;
```

| Situation | Result | Counted as |
|---|---|---|
| The key is new | a row is inserted | `rows_inserted` |
| The key exists with different data | the row is updated | `rows_updated` |
| The key exists with identical data | **nothing is written** | `rows_unchanged` |
| A valid row that cannot be loaded | see below | `rows_skipped` |

Loading the same file twice therefore changes nothing the second time, which makes retries safe. A unique constraint on `(dataset_id, row_key)` guarantees that no copy can exist, even if the code had a bug.

## Rows that are skipped

A valid row is skipped, and counted in `rows_skipped`, if:

- a key value is missing;
- the key is longer than 500 characters;
- the same key already appeared earlier in the same file. **The first row wins**, which matches the `duplicates` rule (it keeps the first copy).

Every valid row is accounted for: `inserted + updated + unchanged + skipped = valid_rows`. A database `CHECK` constraint enforces it.

## Rules that protect the loaded data

- A row that fails a rule is **not loaded and does not touch** the stored version of that record. If record `1` was loaded last week and today's file has it invalid, last week's good version stays.
- The target is never emptied by a load: records missing from a later file are **not deleted**. This is an upsert, not a replace.
- If any **schema** check fails (including a key column missing from a later file), nothing is loaded and the report says so.
- The load runs in the same database transaction as the results. If anything fails, no row is loaded and no result is saved; the run is stored as `FAILED`.

## Design decisions and trade-offs

| Decision | Why | Cost |
|---|---|---|
| Opt-in, off by default | The original design stores no uploaded data, which is the safer default. | Loading must be requested. |
| Rows stored as JSONB text, not typed columns | Any CSV works with no schema to define. | Querying a field needs JSON operators, and nothing is converted to numbers or dates. |
| First duplicate wins | Deterministic, and consistent with the duplicates rule. | A later correction inside the same file is ignored. |
| No deletes | A partial file must never wipe data. | Removing a record needs `DELETE .../records` (all of them). |
| Business key chosen by the user | Only the user knows what identifies a record. | A wrong key merges different records. |

Not covered: updating only some columns, soft deletes, history of changes, and loading files larger than memory (files are processed in memory, in chunks of 1,000 for the database).
