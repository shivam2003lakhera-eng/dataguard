"""Run the upload pipeline on a sample file against the development database.

Usage (project root, venv active):
    python -m scripts.demo_pipeline
    python -m scripts.demo_pipeline cleanup
"""
import sys
from pathlib import Path

from sqlalchemy import delete, select

from app.db.session import get_engine, session_scope
from app.models import Dataset, QualityResult
from app.services.pipeline import create_dataset_from_upload

SAMPLE = Path("sample_data/insurance/policies_bad.csv")
NAME = "demo-pipeline"
RULES = [
    {"name": "policy_id required", "rule_type": "required_values",
     "configuration": {"columns": ["policy_id"]}, "severity": "HIGH"},
    {"name": "premium not negative", "rule_type": "numeric_range",
     "configuration": {"column": "premium", "min": 0}, "severity": "MEDIUM"},
    {"name": "status allowed", "rule_type": "allowed_values",
     "configuration": {"column": "policy_status", "allowed": ["ACTIVE", "EXPIRED", "PENDING"]},
     "severity": "LOW"},
]

print("Database:", get_engine().url.render_as_string(hide_password=True))

if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
    with session_scope() as s:
        print("Deleted datasets:", s.execute(delete(Dataset).where(Dataset.name == NAME)).rowcount)
else:
    with session_scope() as s:
        run = create_dataset_from_upload(s, SAMPLE.read_bytes(), SAMPLE.name, NAME, rules=RULES)
        print("Run", run.id, "->", run.status, "| passed", run.checks_passed, "| failed", run.checks_failed)
        for r in s.scalars(select(QualityResult).where(QualityResult.run_id == run.id)):
            print(f"  {r.status:<4} {r.severity:<6} {r.rule_name:<22} failed={r.rows_failed}/{r.rows_evaluated}")
            