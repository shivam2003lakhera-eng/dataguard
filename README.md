# DataGuard V1

A data quality monitoring platform. Upload a CSV, get an automatic profile, define quality rules, run validation, and review reports in a simple web interface.

> **Local use only.** V1 has no authentication. Do not expose it publicly or use it with sensitive data.

## Features

- CSV upload with validation (type, size, encoding, empty files, bad headers)
- Automatic profile: rows, columns, types, missing values, duplicates, distinct counts, numeric and date min/max
- Six configurable rule types: required columns, no missing values, no duplicate rows, numeric range, allowed values, data type
- Run history and per-rule PASS/FAIL results with severity (LOW, MEDIUM, HIGH)
- Everything persisted in PostgreSQL; raw CSV rows are never stored
- REST API under `/api/v1` and a vanilla JavaScript frontend

## Tech stack

Python 3.13, pandas, FastAPI, Pydantic v2, SQLAlchemy 2.x, psycopg, PostgreSQL 18, HTML/CSS/JavaScript, pytest.

## Setup (Windows PowerShell)

1. **Create the databases** (as the `postgres` superuser, in `psql`):

```sql
   CREATE ROLE dataguard_user WITH LOGIN PASSWORD 'choose_a_password';
   CREATE DATABASE dataguard OWNER dataguard_user;
   CREATE DATABASE dataguard_test OWNER dataguard_user;
```

2. **Create the virtual environment and install packages:**

```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
```

3. **Configure:** copy `.env.example` to `.env` and fill in your password. Use letters, digits and `_` in the password so the URL stays valid. Never commit `.env`.

```powershell
   Copy-Item .env.example .env
```

4. **Check the connection and create the tables:**

```powershell
   python scripts\check_db.py
   python -m scripts.init_db
```

5. **Run the app:**

```powershell
   uvicorn app.main:app --reload
```

   Open http://127.0.0.1:8000/ (interactive API docs at `/docs`).

## Tests

```powershell
python -m pytest -q
```

Tests run against `dataguard_test` only. They refuse to start unless the database is named exactly `dataguard_test` and differs from the development database.

## Try it

Upload `sample_data/insurance/policies_bad.csv` or `sample_data/weather/weather_bad.csv`. Both contain planted problems (blank ids, duplicates, out-of-range numbers, a bad date). These samples are examples; DataGuard works on any CSV.

See [docs/usage.md](docs/usage.md) for a demo walkthrough, [docs/architecture.md](docs/architecture.md) and [docs/database_design.md](docs/database_design.md).