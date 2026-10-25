"""One-off V2 migration: add datasets.user_id (the owner).

Usage (project root, venv active):
    python -m scripts.migrate_v2_ownership

Safe: it does nothing if the column already exists, and refuses to run while
the datasets table contains rows (a required column needs an owner for each row).
"""
from sqlalchemy import inspect, text

from app.db.session import get_engine


def main() -> None:
    engine = get_engine()
    print("Target database:", engine.url.render_as_string(hide_password=True))

    if "user_id" in {c["name"] for c in inspect(engine).get_columns("datasets")}:
        print("Already migrated: datasets.user_id exists.")
        return

    with engine.begin() as conn:  # one transaction: all or nothing
        rows = conn.execute(text("SELECT count(*) FROM datasets")).scalar()
        if rows:
            raise SystemExit(
                f"datasets has {rows} row(s). Delete them first "
                '(python -m scripts.delete_dataset "<name>"), then run this again.'
            )
        conn.execute(text(
            "ALTER TABLE datasets "
            "ADD COLUMN user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE"
        ))
        conn.execute(text("CREATE INDEX ix_datasets_user_id ON datasets (user_id)"))
    print("Migrated: datasets.user_id added.")


if __name__ == "__main__":
    main()