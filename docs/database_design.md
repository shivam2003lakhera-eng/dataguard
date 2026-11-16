# Database design

Think of a filing cabinet: each user has folders (datasets), and each folder holds its profile, rules, runs and results. A folder also holds loaded rows, but only if you ask for that.

| Table | Purpose |
|---|---|
| `users` | Accounts: unique lower-case email and password hash. |
| `user_sessions` | Logins: SHA-256 of the session token and an expiry. |
| `datasets` | One uploaded CSV: owner, name, filename, row and column counts, and optional `key_columns`. |
| `dataset_profiles` | Profile as JSONB. A dataset can have several. |
| `dataset_records` | The loaded rows of a dataset (only if it has key columns): `row_key`, the row as JSONB, and timestamps. |
| `quality_rules` | Configured rules: type, JSONB configuration, severity, enabled flag. |
| `quality_runs` | One validation run: status, times, check counts, row accounting, duration, file hash and loading counts. |
| `quality_results` | One row per rule per run: PASS/FAIL, kind (schema or quality), rows evaluated, failed and rejected, message, JSONB details. |

## Relationships

- A user has many sessions and datasets (`ON DELETE CASCADE`).
- A dataset has many profiles, rules, runs and records (`ON DELETE CASCADE`).
- A run has many results (`ON DELETE CASCADE`).
- A result links to its rule with a nullable `rule_id` (`ON DELETE SET NULL`). Deleting a rule keeps its history, because each result also stores its own `rule_name`.

## What `quality_runs` records

| Columns | Meaning |
|---|---|
| `source_rows`, `valid_rows`, `rejected_rows` | Row accounting. A row failing several rules is counted once. |
| `duration_ms` | Time spent running the checks, loading, and saving. |
| `loadable` | `false` if a schema check failed. |
| `file_sha256` | A hash of the uploaded file. The file itself is not stored. |
| `rows_inserted`, `rows_updated`, `rows_unchanged`, `rows_skipped` | What loading did. All `NULL` if nothing was loaded. |

**`NULL` always means "not measured"**: an old run from before the column existed, or a run that failed. It is never replaced by a made-up zero.

## Constraints

- `CHECK`: email is lower-case; severity in LOW/MEDIUM/HIGH; result status in PASS/FAIL; result category in schema/quality; run status in SUCCESS/COMPLETED_WITH_ISSUES/FAILED; counts, rows, duration and rejected rows are not negative.
- `CHECK` (row accounting): when recorded, `valid_rows + rejected_rows = source_rows`.
- `CHECK` (load accounting): when a load happened, `rows_inserted + rows_updated + rows_unchanged + rows_skipped = valid_rows`.
- `UNIQUE`: `users.email`, `user_sessions.token_hash`, and `(dataset_id, row_key)` on `dataset_records`, so a record can exist only once per dataset.
- `datasets.user_id` is `NOT NULL`: a dataset without an owner cannot exist.
- Indexes on every foreign key (the unique constraint covers `dataset_records.dataset_id`), on `quality_runs.started_at` and on `user_sessions.expires_at`.
- Timestamps use `timestamptz` with a server default.

These are enforced by PostgreSQL itself, so a bug in the application cannot quietly store inconsistent numbers. Tests try to break each of them.

## Why JSONB

Profiles, rule configurations, result details and loaded rows have no fixed shape: any CSV can have any columns. JSONB keeps them queryable without a schema per upload. The trade-off is that loaded values are text and a field is read with JSON operators.

## Schema changes

The schema is versioned with Alembic: see [migrations.md](migrations.md). A test builds a database from the migrations alone and fails if it differs from the SQLAlchemy models.
