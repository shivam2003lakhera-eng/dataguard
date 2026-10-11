from pathlib import Path

import psycopg
from dotenv import dotenv_values
from sqlalchemy.engine import make_url

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

raw = dotenv_values(ENV_FILE).get("DATABASE_URL")
if not raw:
    raise SystemExit(f"DATABASE_URL not found in {ENV_FILE}")

url = make_url(raw)
print("Connecting to:", url.render_as_string(hide_password=True))

# psycopg expects a plain postgresql:// URL, not the SQLAlchemy driver prefix
plain = raw.replace("postgresql+psycopg://", "postgresql://", 1)

try:
    with psycopg.connect(plain, connect_timeout=5) as conn:
        cur = conn.cursor()
        cur.execute("select version()")
        print("Server:", cur.fetchone()[0])
        cur.execute("select current_database(), current_user")
        print("Database / user:", cur.fetchone())
        cur.execute(
            "select datname from pg_database where not datistemplate order by 1"
        )
        print("Databases:", [r[0] for r in cur.fetchall()])
except Exception as e:
    print("CONNECTION FAILED:", type(e).__name__)
    print(str(e).splitlines()[0])
