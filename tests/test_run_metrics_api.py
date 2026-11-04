import pytest
from fastapi.testclient import TestClient

from app.api.routes.auth import login_limiter
from app.db.session import get_db
from app.main import app

API = "/api/v1"
CSV = b"id,amount\n1,5\n,-1\n3,7\n"
RULES = (
    '[{"name": "has columns", "rule_type": "required_columns", "configuration": {"columns": ["id", "amount"]}},'
    ' {"name": "id required", "rule_type": "required_values", "configuration": {"columns": ["id"]}}]'
)


@pytest.fixture
def client(db_session):
    def override():
        yield db_session

    app.dependency_overrides[get_db] = override
    login_limiter.clear()
    browser = TestClient(app, raise_server_exceptions=False)
    registered = browser.post(
        f"{API}/auth/register", json={"email": "metrics@example.com", "password": "correct horse 9"}
    )
    assert registered.status_code == 201
    yield browser
    login_limiter.clear()
    app.dependency_overrides.clear()


def upload(client) -> dict:
    response = client.post(
        f"{API}/datasets/upload",
        files={"file": ("d.csv", CSV, "text/csv")},
        data={"name": "D", "rules": RULES},
    )
    assert response.status_code == 201
    return response.json()


def test_the_report_exposes_row_accounting(client):
    run = upload(client)
    assert (run["source_rows"], run["valid_rows"], run["rejected_rows"]) == (3, 2, 1)
    assert run["loadable"] is True
    assert isinstance(run["duration_ms"], int) and run["duration_ms"] >= 0
    assert len(run["file_sha256"]) == 64


def test_each_result_exposes_its_category_and_rejected_rows(client):
    results = {r["rule_name"]: r for r in upload(client)["results"]}
    assert results["has columns"]["category"] == "schema"
    assert results["has columns"]["rows_rejected"] == 0
    assert results["id required"]["category"] == "quality"
    assert results["id required"]["rows_rejected"] == 1


def test_metrics_are_the_same_when_the_run_is_read_again(client):
    run = upload(client)
    again = client.get(f"{API}/runs/{run['id']}").json()
    for key in ("source_rows", "valid_rows", "rejected_rows", "duration_ms", "loadable", "file_sha256"):
        assert again[key] == run[key]


def test_the_run_list_includes_the_metrics(client):
    upload(client)
    item = client.get(f"{API}/runs").json()["items"][0]
    assert (item["source_rows"], item["rejected_rows"]) == (3, 1)
    assert item["dataset_name"] == "D"


def test_a_rerun_through_the_api_records_its_own_metrics(client):
    first = upload(client)
    rerun = client.post(
        f"{API}/datasets/{first['dataset_id']}/runs", files={"file": ("d.csv", b"id,amount\n1,5\n", "text/csv")}
    ).json()
    assert (rerun["source_rows"], rerun["valid_rows"], rerun["rejected_rows"]) == (1, 1, 0)
    assert rerun["file_sha256"] != first["file_sha256"]
