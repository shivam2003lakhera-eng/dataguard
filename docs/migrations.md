# Database migrations

Schema changes are made with Alembic. The files in `migrations/versions/` are a history: never edit one that has been applied, add a new one instead.

| Revision | What it does |
|---|---|
| `0001_baseline` | The V2 schema: users, sessions, datasets, profiles, rules, runs, results. |
| `0002_run_metrics` | Run metrics (source, valid and rejected rows, duration, loadable, file hash) and the result category. Old rows are kept and classified. |
| `0003_record_loading` | Opt-in loading: `datasets.key_columns`, the `dataset_records` table, and the loading counts on runs. Nothing changes for existing data. |

## Commands (project root, venv active)

| Task | Command |
|---|---|
| Create or update a database | `alembic upgrade head` |
| Show the current version | `alembic current` |
| Do the models and the database agree? | `alembic check` |
| Use the test database | add `-x db=test`, for example `alembic -x db=test upgrade head` |
| Adopt a database made before Alembic | `alembic stamp 0001_baseline`, then `alembic upgrade head` |

Run these **one at a time and read the output**. `alembic stamp` only changes the version label: it does not change the tables. Stamp the revision that matches your tables. Stamping `head` on a database that lacks the newer changes claims something false, and repeating a stamp followed by an upgrade fails with "column already exists".

## Rules

- Migrations never import application code, so they stay valid when the models change.
- `tests/test_migrations.py` rebuilds the test database from the migrations only and fails if the result differs from the SQLAlchemy models. It also upgrades a database that already holds data, and reverses and re-applies the latest migrations.
- `alembic downgrade` deletes data. Use it on the test database only.
- A new column on an existing table should be nullable (or have a default) so existing rows stay valid. A `NULL` metric means "not measured", never zero.
- Back up before upgrading a database you care about: `pg_dump -U dataguard_user -h localhost dataguard -f backup.sql`. Do not commit the backup (`*.sql` is git-ignored).
