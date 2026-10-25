"""Inspect the development database.

Usage (project root, venv active):
    python -m scripts.persistence_check show
    python -m scripts.persistence_check cleanup
    python -m scripts.persistence_check schema
"""
import sys

from sqlalchemy import delete, inspect, text

from app.db.session import get_engine, session_scope
from app.models import Dataset

NAME = "persist-check"


def main(action: str) -> None:
    print("Database:", get_engine().url.render_as_string(hide_password=True))

    if action == "show":
        # Plain SQL on purpose: works even if the table is missing newer columns.
        with get_engine().connect() as conn:
            names = conn.execute(text("SELECT name FROM datasets ORDER BY id")).scalars().all()
        print("Datasets:", names)
    elif action == "cleanup":
        with session_scope() as s:
            result = s.execute(delete(Dataset).where(Dataset.name == NAME))
        print("Deleted rows:", result.rowcount)
    elif action == "schema":
        insp = inspect(get_engine())
        table = "quality_results"
        print("Columns:", [c["name"] for c in insp.get_columns(table)])
        print("Checks:", sorted(c["name"] for c in insp.get_check_constraints(table)))
        for fk in insp.get_foreign_keys(table):
            print("FK:", fk["constrained_columns"], "->", fk["referred_table"],
                  "ON DELETE", fk["options"].get("ondelete"))
        print("Indexes:", sorted(i["name"] for i in insp.get_indexes(table)))
    else:
        raise SystemExit("Use: show | cleanup | schema")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")