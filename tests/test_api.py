import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app

SAMPLES = Path(__file__).resolve().parent.parent / "sample_data"
BAD = (SAMPLES / "insurance" / "policies_bad.csv").read_bytes()
GOOD = b"policy_id,premium\nP1,10\nP2,20\n"
API = "/api/v1"

ID_REQUIRED = {
    "name": "id required", "rule_type": "required_values",
    "configuration": {"columns": ["policy_id"]}, "severity": "HIGH",
}

@pytest.fixture
def client(db_session):
    def override():
        yield db_session

    app.dependency_overrides[get_db] = override
    browser = TestClient(app, raise_server_exceptions=False)
    browser.post(
        f"{API}/auth/register",
        json={"email": "owner@example.com", "password": "correct horse 9"},
    )  # registering also logs in: the cookie stays in this client
    yield browser
    app.dependency_overrides.clear()


def csv_file(content=GOOD, filename="data.csv"):
    return {"file": (filename, content, "text/csv")}


def upload(client, content=BAD, filename="policies_bad.csv", name="Policies", rules=None):
    data = {"name": name}
    if rules is not None:
        data["rules"] = json.dumps(rules)
    return client.post(f"{API}/datasets/upload", files=csv_file(content, filename), data=data)


def code(response) -> str:
    return response.json()["error"]["code"]


def new_dataset(client, rules=None, content=GOOD) -> int:
    return upload(client, content, "d.csv", "D", rules).json()["dataset_id"]


# ---------- Health and error format ----------

def test_health_ok(client):
    r = client.get(f"{API}/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok"}


def test_unknown_route_uses_standard_error_format(client):
    r = client.get(f"{API}/nope")
    assert r.status_code == 404
    assert code(r) == "http_error"


# ---------- Upload ----------

def test_upload_with_rules_returns_report(client):
    r = upload(client, rules=[ID_REQUIRED])
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "COMPLETED_WITH_ISSUES"
    assert body["checks_failed"] == 1 and body["checks_passed"] == 0
    assert len(body["results"]) == 1
    assert body["results"][0]["status"] == "FAIL"
    assert body["results"][0]["rows_failed"] == 1

    rules = client.get(f"{API}/datasets/{body['dataset_id']}/rules").json()
    assert len(rules) == 1 and rules[0]["name"] == "id required"


def test_upload_without_rules_is_success(client):
    r = upload(client, GOOD, "good.csv")
    assert r.status_code == 201
    assert r.json()["status"] == "SUCCESS"
    assert r.json()["results"] == []


def test_upload_rejects_non_csv(client):
    r = upload(client, b"a,b\n1,2\n", "data.json")
    assert r.status_code == 422
    assert code(r) == "unsupported_format"


def test_upload_rejects_empty_file(client):
    r = upload(client, b"", "empty.csv")
    assert r.status_code == 422
    assert code(r) == "invalid_source_data"


def test_upload_rejects_oversized_file(client, monkeypatch):
    monkeypatch.setattr("app.api.deps.get_settings", lambda: SimpleNamespace(max_file_size_mb=1))
    big = b"a,b\n" + b"1,2\n" * 300_000  # about 1.2 MB
    r = upload(client, big, "big.csv")
    assert r.status_code == 413
    assert code(r) == "file_too_large"


def test_upload_requires_name(client):
    r = client.post(f"{API}/datasets/upload", files=csv_file())
    assert r.status_code == 422
    assert code(r) == "validation_error"
    assert r.json()["error"]["details"]["errors"]


def test_upload_requires_file(client):
    r = client.post(f"{API}/datasets/upload", data={"name": "x"})
    assert r.status_code == 422
    assert code(r) == "validation_error"


def test_upload_invalid_rules_json_saves_nothing(client):
    r = client.post(
        f"{API}/datasets/upload", files=csv_file(BAD, "p.csv"),
        data={"name": "x", "rules": "this is not json"},
    )
    assert r.status_code == 422
    assert code(r) == "invalid_configuration"
    assert client.get(f"{API}/datasets").json()["total"] == 0


def test_upload_invalid_rule_config_saves_nothing(client):
    bad_rule = {"name": "bad", "rule_type": "numeric_range",
                "configuration": {"column": "premium"}, "severity": "LOW"}
    r = upload(client, rules=[bad_rule])
    assert r.status_code == 422
    assert code(r) == "invalid_configuration"
    assert client.get(f"{API}/datasets").json()["total"] == 0


def test_unexpected_error_returns_generic_500(client, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("secret detail F:\\server\\path")

    monkeypatch.setattr("app.api.routes.datasets.create_dataset_from_upload", boom)
    r = upload(client)
    assert r.status_code == 500
    assert code(r) == "internal_error"
    assert "secret" not in r.text and "Traceback" not in r.text and "F:" not in r.text


# ---------- Datasets ----------

def test_list_datasets_is_paginated(client):
    for i in range(3):
        upload(client, GOOD, "g.csv", name=f"D{i}")

    page1 = client.get(f"{API}/datasets?limit=2").json()
    assert page1["total"] == 3 and page1["limit"] == 2 and page1["offset"] == 0
    assert [d["name"] for d in page1["items"]] == ["D2", "D1"]

    page2 = client.get(f"{API}/datasets?limit=2&offset=2").json()
    assert [d["name"] for d in page2["items"]] == ["D0"]


@pytest.mark.parametrize("query", ["limit=0", "limit=1000", "offset=-1"])
def test_list_rejects_bad_pagination(client, query):
    r = client.get(f"{API}/datasets?{query}")
    assert r.status_code == 422
    assert code(r) == "validation_error"


def test_get_dataset(client):
    ds_id = upload(client).json()["dataset_id"]
    body = client.get(f"{API}/datasets/{ds_id}").json()
    assert body["name"] == "Policies"
    assert body["original_filename"] == "policies_bad.csv"
    assert body["row_count"] == 8 and body["column_count"] == 5
    assert body["created_at"]


def test_get_unknown_dataset_is_404(client):
    r = client.get(f"{API}/datasets/999999")
    assert r.status_code == 404
    assert code(r) == "not_found"


def test_dataset_id_must_be_integer(client):
    r = client.get(f"{API}/datasets/abc")
    assert r.status_code == 422
    assert code(r) == "validation_error"


def test_get_profile(client):
    ds_id = upload(client).json()["dataset_id"]
    body = client.get(f"{API}/datasets/{ds_id}/profile").json()
    assert body["dataset_id"] == ds_id
    assert body["profile_data"]["row_count"] == 8
    assert len(body["profile_data"]["columns"]) == 5


def test_profile_of_unknown_dataset_is_404(client):
    assert client.get(f"{API}/datasets/999999/profile").status_code == 404


# ---------- Rules ----------

def test_create_and_list_rules(client):
    ds_id = new_dataset(client)
    r = client.post(f"{API}/datasets/{ds_id}/rules", json=ID_REQUIRED)
    assert r.status_code == 201
    body = r.json()
    assert body["id"] and body["enabled"] is True and body["severity"] == "HIGH"
    assert len(client.get(f"{API}/datasets/{ds_id}/rules").json()) == 1


def test_create_rule_with_invalid_config_is_rejected(client):
    ds_id = new_dataset(client)
    bad = {"name": "bad", "rule_type": "numeric_range", "configuration": {"column": "x"}}
    r = client.post(f"{API}/datasets/{ds_id}/rules", json=bad)
    assert r.status_code == 422
    assert code(r) == "invalid_configuration"
    assert client.get(f"{API}/datasets/{ds_id}/rules").json() == []


def test_create_rule_with_invalid_severity_is_rejected(client):
    ds_id = new_dataset(client)
    r = client.post(f"{API}/datasets/{ds_id}/rules", json={**ID_REQUIRED, "severity": "CRITICAL"})
    assert r.status_code == 422
    assert code(r) == "invalid_configuration"


def test_create_rule_on_unknown_dataset_is_404(client):
    r = client.post(f"{API}/datasets/999999/rules", json=ID_REQUIRED)
    assert r.status_code == 404


def test_patch_rule_toggles_enabled(client):
    ds_id = new_dataset(client)
    rule_id = client.post(f"{API}/datasets/{ds_id}/rules", json=ID_REQUIRED).json()["id"]
    r = client.patch(f"{API}/rules/{rule_id}", json={"enabled": False})
    assert r.status_code == 200
    assert r.json()["enabled"] is False


def test_patch_rule_updates_configuration(client):
    ds_id = new_dataset(client)
    rule_id = client.post(f"{API}/datasets/{ds_id}/rules", json=ID_REQUIRED).json()["id"]
    r = client.patch(
        f"{API}/rules/{rule_id}",
        json={"configuration": {"columns": ["premium"]}, "severity": "low"},
    )
    assert r.status_code == 200
    assert r.json()["configuration"] == {"columns": ["premium"]}
    assert r.json()["severity"] == "LOW"


def test_patch_with_invalid_configuration_keeps_stored_rule(client):
    ds_id = new_dataset(client)
    rule_id = client.post(f"{API}/datasets/{ds_id}/rules", json=ID_REQUIRED).json()["id"]
    r = client.patch(f"{API}/rules/{rule_id}", json={"configuration": {"columns": []}})
    assert r.status_code == 422
    assert code(r) == "invalid_configuration"
    stored = client.get(f"{API}/datasets/{ds_id}/rules").json()[0]
    assert stored["configuration"] == {"columns": ["policy_id"]}


def test_patch_cannot_change_rule_type(client):
    ds_id = new_dataset(client)
    rule_id = client.post(f"{API}/datasets/{ds_id}/rules", json=ID_REQUIRED).json()["id"]
    r = client.patch(f"{API}/rules/{rule_id}", json={"rule_type": "duplicates"})
    assert r.status_code == 422
    assert code(r) == "validation_error"


def test_patch_unknown_rule_is_404(client):
    assert client.patch(f"{API}/rules/999999", json={"enabled": False}).status_code == 404


def test_delete_rule(client):
    ds_id = new_dataset(client)
    rule_id = client.post(f"{API}/datasets/{ds_id}/rules", json=ID_REQUIRED).json()["id"]
    assert client.delete(f"{API}/rules/{rule_id}").status_code == 204
    assert client.delete(f"{API}/rules/{rule_id}").status_code == 404
    assert client.get(f"{API}/datasets/{ds_id}/rules").json() == []


# ---------- Runs ----------

def test_new_run_with_new_file(client):
    first = upload(client, BAD, "p.csv", "P", rules=[ID_REQUIRED]).json()
    ds_id = first["dataset_id"]
    r = client.post(f"{API}/datasets/{ds_id}/runs", files=csv_file(GOOD))
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "SUCCESS"
    assert body["checks_passed"] == 1 and body["checks_failed"] == 0
    assert body["dataset_id"] == ds_id and body["id"] != first["id"]


def test_disabled_rule_is_not_run(client):
    ds_id = upload(client, BAD, "p.csv", "P", rules=[ID_REQUIRED]).json()["dataset_id"]
    rule_id = client.get(f"{API}/datasets/{ds_id}/rules").json()[0]["id"]
    client.patch(f"{API}/rules/{rule_id}", json={"enabled": False})

    body = client.post(f"{API}/datasets/{ds_id}/runs", files=csv_file(BAD, "p.csv")).json()
    assert body["checks_passed"] == 0 and body["checks_failed"] == 0
    assert body["status"] == "SUCCESS"


def test_run_on_unknown_dataset_is_404(client):
    r = client.post(f"{API}/datasets/999999/runs", files=csv_file())
    assert r.status_code == 404
    assert code(r) == "not_found"


def test_list_runs_newest_first(client):
    first = upload(client, BAD, "p.csv", "P", rules=[ID_REQUIRED]).json()
    ds_id = first["dataset_id"]
    second = client.post(f"{API}/datasets/{ds_id}/runs", files=csv_file(GOOD)).json()

    page = client.get(f"{API}/datasets/{ds_id}/runs").json()
    assert page["total"] == 2
    assert [run["id"] for run in page["items"]] == [second["id"], first["id"]]
    assert "results" not in page["items"][0]

    only_one = client.get(f"{API}/datasets/{ds_id}/runs?limit=1&offset=1").json()
    assert [run["id"] for run in only_one["items"]] == [first["id"]]


def test_list_runs_of_unknown_dataset_is_404(client):
    assert client.get(f"{API}/datasets/999999/runs").status_code == 404


def test_get_run_with_results(client):
    run_id = upload(client, rules=[ID_REQUIRED]).json()["id"]
    body = client.get(f"{API}/runs/{run_id}").json()
    assert body["status"] == "COMPLETED_WITH_ISSUES"
    assert body["completed_at"] is not None
    assert body["results"][0]["rule_name"] == "id required"
    assert body["results"][0]["rows_evaluated"] == 8


def test_get_unknown_run_is_404(client):
    r = client.get(f"{API}/runs/999999")
    assert r.status_code == 404
    assert code(r) == "not_found"


def test_run_rejects_invalid_file_and_creates_no_run(client):
    ds_id = new_dataset(client)
    r = client.post(f"{API}/datasets/{ds_id}/runs", files=csv_file(b"", "empty.csv"))
    assert r.status_code == 422
    assert client.get(f"{API}/datasets/{ds_id}/runs").json()["total"] == 1