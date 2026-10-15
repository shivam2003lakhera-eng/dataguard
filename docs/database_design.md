# Database design

Think of a filing cabinet: one folder per dataset, with its profile, rules, runs and results inside.

| Table | Purpose |
|---|---|
| `datasets` | One uploaded CSV: name, filename, row and column counts. No rows stored. |
| `dataset_profiles` | Profile as JSONB. A dataset can have several. |
| `quality_rules` | Configured rules: type, JSONB configuration, severity, enabled flag. |
| `quality_runs` | One validation run: status, start and end time, passed and failed counts, error message. |
| `quality_results` | One row per rule per run: PASS/FAIL, rows evaluated and failed, message, JSONB details. |

## Relationships

- A dataset has many profiles, rules and runs (`ON DELETE CASCADE`).
- A run has many results (`ON DELETE CASCADE`).
- A result links to its rule with a nullable `rule_id` (`ON DELETE SET NULL`). Deleting a rule keeps its history, because each result also stores its own `rule_name`.

## Constraints

- `CHECK`: severity in LOW/MEDIUM/HIGH; result status in PASS/FAIL; run status in SUCCESS/COMPLETED_WITH_ISSUES/FAILED; counts are not negative.
- Indexes on every foreign key and on `quality_runs.started_at`.
- Timestamps use `timestamptz` with a server default.

## Setup

Tables are created by `python -m scripts.init_db`, which is safe to repeat. Alembic is installed and may replace it later.