"""Create the DataGuard tables in the development database.

Usage (from the project root, venv active):
    python -m scripts.init_db

Safe to run more than once: existing tables are left untouched.
Alembic migrations can replace this once the models stabilise.
"""
from sqlalchemy import inspect

import app.models  # noqa: F401  (registers all tables)
from app.db.base import Base
from app.db.session import get_engine


def main() -> None:
    engine = get_engine()
    print("Target database:", engine.url.render_as_string(hide_password=True))
    Base.metadata.create_all(engine)
    print("Tables:", sorted(inspect(engine).get_table_names()))


if __name__ == "__main__":
    main()