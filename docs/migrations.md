# Database migrations

Schema changes are made with Alembic. The files in `migrations/versions/` are a history: never edit one that has been applied, add a new one instead.

| Revision | What it does |
|---|---|
| `0001_baseline` | The V2 schema: users, sessions, datasets, profiles, rules, runs, results. |
| `0002_run_metrics` | Run metrics (source, valid and rejected rows, duration, loadable, file hash) and the result category. Old rows are kept and classified. |

## Commands (project root, venv active)

| Task | Command |
|---|---|
| Create or update a database | `alembic upgrade head` |
| Show the current version | `alembic current` |
| Do the models and the database agree? | `alembic check` |
| Use the test database | add `-x db=test`, for example `alembic -x db=test upgrade head` |
| Adopt a database made earlier by `create_all` | `alembic stamp 0001_baseline`, then `alembic upgrade head` |

Use the revision name `0001_baseline` when stamping a database that was created before Alembic: stamping `head` would claim that newer changes were applied when they were not.

## Rules

- Migrations never import application code, so they stay valid when the models change.
- `tests/test_migrations.py` rebuilds the test database from the migrations only and fails if the result differs from the SQLAlchemy models. It also upgrades a database that already holds data.
- `alembic downgrade` deletes data. Use it on the test database only.
- New databases: run `alembic upgrade head`. The older `scripts/init_db.py` and `scripts/migrate_v2_ownership.py` are superseded.
- A new column on an existing table should be nullable (or have a default) so existing rows stay valid. A NULL metric means "not measured", never zero.
