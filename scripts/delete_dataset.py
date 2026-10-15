"""Delete datasets by exact name (children are removed by cascade).

Usage: python -m scripts.delete_dataset "browser-test"
"""
import sys

from sqlalchemy import delete

from app.db.session import get_engine, session_scope
from app.models import Dataset

if len(sys.argv) != 2:
    raise SystemExit('Usage: python -m scripts.delete_dataset "<exact name>"')

print("Database:", get_engine().url.render_as_string(hide_password=True))
with session_scope() as s:
    print("Deleted:", s.execute(delete(Dataset).where(Dataset.name == sys.argv[1])).rowcount)