import pytest
from fastapi.testclient import TestClient

from app.api.routes.auth import login_limiter
from app.db.session import get_db
from app.main import app

API = "/api/v1"
CSV = b"id,name,amount\n1,Asha,10\n2,Ravi,20\n3,Meena,-5\n"
RULES = '[{"name": "amount not negative", "rule_type": "numeric_range", "configuration": {"column": "amount", "min": 0}}]'


def sign_up(email: str) -> TestClient:
    browser = TestClient(app, raise_server_exceptions=False)
    response = browser.post(f"{API}/auth/register", json={"email": email, "password": "correct horse 9"})
    assert response.status_code == 201
    return browser


@pytest.fixture
def client(db_session):
    def override():
        yield db_session

    app.dependency_overrides[get_db] = override
    login_limiter.clear()
    yield sign_up("loader@example.com")
    login_limiter.clear()
    app.dependency_overrides.clear()


def upload(client, keys="id", content=CSV):
    data = {"name": "D", "rules": RULES}
    if keys is not None:
        data["key_columns"] = keys
    return client.post(f"{API}/datasets/upload", files={"file": ("d.csv", content, "text/csv")}, data=data)


def records(client, dataset_id, query=""):
    return client.get(f"{API}/datasets/{dataset_id}/records{query}")


def code(response) -> str:
    return response.json()["error"]["code"]


def test_upload_with_key_columns_loads_the_valid_rows(client):
    run = upload(client).json()
    assert (run["rows_inserted"], run["rows_updated"], run["rows_unchanged"], run["rows_skipped"]) == (2, 0, 0, 0)
    page = records(client, run["dataset_id"]).json()
    assert page["total"] == 2
    assert [item["data"]["name"] for item in page["items"]] == ["Asha", "Ravi"]
    assert page["items"][0]["row_key"] == '["1"]'
    assert client.get(f"{API}/datasets/{run['dataset_id']}").json()["key_columns"] == ["id"]


def test_upload_without_key_columns_stores_no_rows(client):
    run = upload(client, keys=None).json()
    assert run["rows_inserted"] is None
    assert records(client, run["dataset_id"]).json()["total"] == 0
    assert client.get(f"{API}/datasets/{run['dataset_id']}").json()["key_columns"] is None


def test_running_the_same_file_again_through_the_api_changes_nothing(client):
    first = upload(client).json()
    again = client.post(
        f"{API}/datasets/{first['dataset_id']}/runs", files={"file": ("d.csv", CSV, "text/csv")}
    ).json()
    assert (again["rows_inserted"], again["rows_updated"], again["rows_unchanged"]) == (0, 0, 2)
    assert records(client, first["dataset_id"]).json()["total"] == 2


def test_key_columns_can_be_set_later_and_apply_to_the_next_run(client):
    first = upload(client, keys=None).json()
    dataset_id = first["dataset_id"]
    patched = client.patch(f"{API}/datasets/{dataset_id}", json={"key_columns": ["id"]})
    assert patched.status_code == 200 and patched.json()["key_columns"] == ["id"]

    rerun = client.post(f"{API}/datasets/{dataset_id}/runs", files={"file": ("d.csv", CSV, "text/csv")}).json()
    assert rerun["rows_inserted"] == 2


def test_turning_loading_off_keeps_the_records_and_deleting_removes_them(client):
    dataset_id = upload(client).json()["dataset_id"]
    off = client.patch(f"{API}/datasets/{dataset_id}", json={"key_columns": None})
    assert off.status_code == 200 and off.json()["key_columns"] is None
    assert records(client, dataset_id).json()["total"] == 2          # kept

    assert client.delete(f"{API}/datasets/{dataset_id}/records").status_code == 204
    assert records(client, dataset_id).json()["total"] == 0
    assert client.delete(f"{API}/datasets/{dataset_id}/records").status_code == 204   # repeatable
    assert client.get(f"{API}/datasets/{dataset_id}").status_code == 200             # the dataset stays


def test_records_are_paginated(client):
    dataset_id = upload(client).json()["dataset_id"]
    second = records(client, dataset_id, "?limit=1&offset=1").json()
    assert second["total"] == 2 and len(second["items"]) == 1
    assert second["items"][0]["row_key"] == '["2"]'
    assert records(client, dataset_id, "?limit=0").status_code == 422


@pytest.mark.parametrize("keys", ["id,,name", " , ", "id,id"])
def test_invalid_key_columns_on_upload_are_rejected(client, keys):
    response = upload(client, keys=keys)
    assert response.status_code == 422 and code(response) == "invalid_configuration"
    assert client.get(f"{API}/datasets").json()["total"] == 0     # nothing was saved


def test_a_blank_key_columns_field_means_no_loading(client):
    run = upload(client, keys="   ")
    assert run.status_code == 201
    assert run.json()["rows_inserted"] is None
    assert records(client, run.json()["dataset_id"]).json()["total"] == 0


def test_a_key_column_that_is_not_in_the_file_is_rejected_and_nothing_is_saved(client):
    response = upload(client, keys="nope")
    assert response.status_code == 422 and code(response) == "invalid_configuration"
    assert client.get(f"{API}/datasets").json()["total"] == 0


@pytest.mark.parametrize("body", [{"key_columns": []}, {"key_columns": ["id", "id"]}, {"key_columns": [" "]}])
def test_invalid_key_columns_on_patch_are_rejected(client, body):
    dataset_id = upload(client, keys=None).json()["dataset_id"]
    response = client.patch(f"{API}/datasets/{dataset_id}", json=body)
    assert response.status_code == 422 and code(response) == "invalid_configuration"
    assert client.get(f"{API}/datasets/{dataset_id}").json()["key_columns"] is None


@pytest.mark.parametrize("body", [{}, {"key_columns": "id"}, {"key_columns": ["id"], "extra": 1}])
def test_a_malformed_patch_body_is_a_validation_error(client, body):
    dataset_id = upload(client, keys=None).json()["dataset_id"]
    response = client.patch(f"{API}/datasets/{dataset_id}", json=body)
    assert response.status_code == 422 and code(response) == "validation_error"


def test_another_users_records_cannot_be_read_changed_or_deleted(client):
    dataset_id = upload(client).json()["dataset_id"]
    other = sign_up("someone-else@example.com")

    assert records(other, dataset_id).status_code == 404
    assert other.patch(f"{API}/datasets/{dataset_id}", json={"key_columns": None}).status_code == 404
    assert other.delete(f"{API}/datasets/{dataset_id}/records").status_code == 404
    assert records(client, dataset_id).json()["total"] == 2          # untouched
    assert client.get(f"{API}/datasets/{dataset_id}").json()["key_columns"] == ["id"]


def test_loading_endpoints_need_a_login(client):
    dataset_id = upload(client).json()["dataset_id"]
    stranger = TestClient(app, raise_server_exceptions=False)
    assert records(stranger, dataset_id).status_code == 401
    assert stranger.patch(f"{API}/datasets/{dataset_id}", json={"key_columns": None}).status_code == 401
    assert stranger.delete(f"{API}/datasets/{dataset_id}/records").status_code == 401
