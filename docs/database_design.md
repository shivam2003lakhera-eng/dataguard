# Database design

Think of a filing cabinet: each user has folders (datasets), and each folder holds its profile, rules, runs and results.

| Table | Purpose |
|---|---|
| `users` | Accounts: unique lower-case email and password hash. |
| `user_sessions` | Logins: SHA-256 of the session token and an expiry. |
| `datasets` | One uploaded CSV: owner, name, filename, row and column counts. No rows stored. |
| `dataset_profiles` | Profile as JSONB. A dataset can have several. |
| `quality_rules` | Configured rules: type, JSONB configuration, severity, enabled flag. |
| `quality_runs` | One validation run: status, start and end time, passed and failed counts, error message. |
| `quality_results` | One row per rule per run: PASS/FAIL, rows evaluated and failed, message, JSONB details. |

## Relationships

- A user has many sessions and datasets (`ON DELETE CASCADE`).
- A dataset has many profiles, rules and runs (`ON DELETE CASCADE`).
- A run has many results (`ON DELETE CASCADE`).
- A result links to its rule with a nullable `rule_id` (`ON DELETE SET NULL`). Deleting a rule keeps its history, because each result also stores its own `rule_name`.

## Constraints

- `CHECK`: email is lower-case; severity in LOW/MEDIUM/HIGH; result status in PASS/FAIL; run status in SUCCESS/COMPLETED_WITH_ISSUES/FAILED; counts are not negative.
- `UNIQUE`: `users.email` and `user_sessions.token_hash`.
- `datasets.user_id` is `NOT NULL`: a dataset without an owner cannot exist.
- Indexes on every foreign key, on `quality_runs.started_at` and on `user_sessions.expires_at`.
- Timestamps use `timestamptz` with a server default.

## Setup

Tables are created by `python -m scripts.init_db`, which is safe to repeat. A V1 database also needs `python -m scripts.migrate_v2_ownership`. Alembic is installed and may replace these scripts later.