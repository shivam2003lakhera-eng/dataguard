import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.api.routes.auth import login_limiter
from app.db.session import get_db
from app.main import app
from app.models import Dataset, User

API = "/api/v1"
PASSWORD = "correct horse 9"
GOOD = b"policy_id,premium\nP1,10\nP2,20\n"
BAD = b"policy_id,premium\n,10\nP2,-5\n"  # one blank policy_id
ID_REQUIRED = {
    "name": "id required", "rule_type": "required_values",
    "configuration": {"columns": ["policy_id"]}, "severity": "HIGH",
}
CSV = {"file": ("d.csv", GOOD, "text/csv")}


def browser() -> TestClient:
    """A browser with its own, empty cookie jar."""
    return TestClient(app, raise_server_exceptions=False)


def sign_up(email: str) -> TestClient:
    client = browser()
    r = client.post(f"{API}/auth/register", json={"email": email, "password": PASSWORD})
    assert r.status_code == 201
    return client


@pytest.fixture
def world(db_session):
    def override():
        yield db_session

    app.dependency_overrides[get_db] = override
    login_limiter.clear()
    yield SimpleNamespace(
        alice=sign_up("alice@example.com"),
        bob=sign_up("bob@example.com"),
        anonymous=browser(),
        db=db_session,
    )
    login_limiter.clear()
    app.dependency_overrides.clear()


def upload(client, content=BAD, name="Data", rules=None):
    data = {"name": name}
    if rules is not None:
        data["rules"] = json.dumps(rules)
    return client.post(
        f"{API}/datasets/upload", files={"file": ("d.csv", content, "text/csv")}, data=data
    )


def code(response) -> str:
    return response.json()["error"]["code"]


# ---------- Login is required ----------

PROTECTED = [
    ("get", "/datasets", {}),
    ("post", "/datasets/upload", {"files": CSV, "data": {"name": "x"}}),
    ("get", "/datasets/1", {}),
    ("get", "/datasets/1/profile", {}),
    ("get", "/datasets/1/rules", {}),
    ("post", "/datasets/1/rules", {"json": ID_REQUIRED}),
    ("patch", "/rules/1", {"json": {"enabled": False}}),
    ("delete", "/rules/1", {}),
    ("post", "/datasets/1/runs", {"files": CSV}),
    ("get", "/datasets/1/runs", {}),
    ("get", "/runs", {}),
    ("get", "/runs/1", {}),
]


@pytest.mark.parametrize("method, path, kwargs", PROTECTED)
def test_every_data_endpoint_requires_login(world, method, path, kwargs):
    r = getattr(world.anonymous, method)(f"{API}{path}", **kwargs)
    assert r.status_code == 401
    assert code(r) == "not_authenticated"


def test_logging_out_blocks_further_access(world):
    assert world.alice.get(f"{API}/datasets").status_code == 200
    world.alice.post(f"{API}/auth/logout")
    assert world.alice.get(f"{API}/datasets").status_code == 401


# ---------- Ownership ----------

def test_uploaded_dataset_belongs_to_the_uploader(world):
    ds_id = upload(world.alice).json()["dataset_id"]
    alice_id = world.alice.get(f"{API}/auth/me").json()["id"]
    assert world.db.get(Dataset, ds_id).user_id == alice_id


def test_each_user_lists_only_their_own_datasets(world):
    upload(world.alice, name="A1")
    upload(world.alice, name="A2")
    upload(world.bob, name="B1")

    alice = world.alice.get(f"{API}/datasets").json()
    bob = world.bob.get(f"{API}/datasets").json()
    assert alice["total"] == 2 and {d["name"] for d in alice["items"]} == {"A1", "A2"}
    assert bob["total"] == 1 and bob["items"][0]["name"] == "B1"


def test_two_users_can_use_the_same_dataset_name(world):
    assert upload(world.alice, name="Shared").status_code == 201
    assert upload(world.bob, name="Shared").status_code == 201


BOBS_DATASET = [
    ("get", "/datasets/{id}", {}),
    ("get", "/datasets/{id}/profile", {}),
    ("get", "/datasets/{id}/rules", {}),
    ("post", "/datasets/{id}/rules", {"json": ID_REQUIRED}),
    ("get", "/datasets/{id}/runs", {}),
    ("post", "/datasets/{id}/runs", {"files": CSV}),
]


@pytest.mark.parametrize("method, path, kwargs", BOBS_DATASET)
def test_another_users_dataset_is_not_found(world, method, path, kwargs):
    bobs_id = upload(world.bob).json()["dataset_id"]

    r = getattr(world.alice, method)(f"{API}{path.format(id=bobs_id)}", **kwargs)
    assert r.status_code == 404
    assert code(r) == "not_found"

    # Bob's data was not touched by Alice's attempt
    assert world.bob.get(f"{API}/datasets/{bobs_id}/rules").json() == []
    assert world.bob.get(f"{API}/datasets/{bobs_id}/runs").json()["total"] == 1


def test_other_users_data_looks_the_same_as_missing_data(world):
    bobs_id = upload(world.bob).json()["dataset_id"]
    other = world.alice.get(f"{API}/datasets/{bobs_id}")
    missing = world.alice.get(f"{API}/datasets/999999")

    assert other.status_code == missing.status_code == 404
    assert other.json()["error"]["code"] == missing.json()["error"]["code"]
    assert other.json()["error"]["message"] == missing.json()["error"]["message"]


def test_cannot_change_or_delete_another_users_rule(world):
    bobs_id = upload(world.bob, rules=[ID_REQUIRED]).json()["dataset_id"]
    rule_id = world.bob.get(f"{API}/datasets/{bobs_id}/rules").json()[0]["id"]

    assert world.alice.patch(f"{API}/rules/{rule_id}", json={"enabled": False}).status_code == 404
    assert world.alice.delete(f"{API}/rules/{rule_id}").status_code == 404

    rule = world.bob.get(f"{API}/datasets/{bobs_id}/rules").json()[0]
    assert rule["enabled"] is True


def test_cannot_read_another_users_run(world):
    run_id = upload(world.bob).json()["id"]
    assert world.alice.get(f"{API}/runs/{run_id}").status_code == 404
    assert world.bob.get(f"{API}/runs/{run_id}").status_code == 200


# ---------- My runs ----------

def test_my_runs_are_mine_newest_first_with_dataset_name(world):
    first = upload(world.alice, name="First").json()
    again = world.alice.post(f"{API}/datasets/{first['dataset_id']}/runs", files=CSV).json()
    upload(world.bob, name="Bobs")

    page = world.alice.get(f"{API}/runs").json()
    assert page["total"] == 2
    assert [r["id"] for r in page["items"]] == [again["id"], first["id"]]
    assert {r["dataset_name"] for r in page["items"]} == {"First"}
    assert "results" not in page["items"][0]


def test_my_runs_can_be_filtered_by_status(world):
    upload(world.alice, content=BAD, name="Bad", rules=[ID_REQUIRED])  # has a failing check
    upload(world.alice, content=GOOD, name="Good")                      # no rules: SUCCESS

    issues = world.alice.get(f"{API}/runs?status=COMPLETED_WITH_ISSUES").json()
    ok = world.alice.get(f"{API}/runs?status=SUCCESS").json()
    assert issues["total"] == 1 and issues["items"][0]["dataset_name"] == "Bad"
    assert ok["total"] == 1 and ok["items"][0]["dataset_name"] == "Good"


def test_my_runs_rejects_an_unknown_status(world):
    r = world.alice.get(f"{API}/runs?status=DONE")
    assert r.status_code == 422
    assert code(r) == "validation_error"


def test_my_runs_are_paginated(world):
    for i in range(3):
        upload(world.alice, content=GOOD, name=f"D{i}")

    first = world.alice.get(f"{API}/runs?limit=2").json()
    assert first["total"] == 3 and len(first["items"]) == 2
    assert len(world.alice.get(f"{API}/runs?limit=2&offset=2").json()["items"]) == 1
    assert world.alice.get(f"{API}/runs?limit=0").status_code == 422


# ---------- Database level ----------

def test_deleting_a_user_removes_their_datasets(world):
    upload(world.alice, name="A")
    upload(world.bob, name="B")

    world.db.execute(delete(User).where(User.email == "alice@example.com"))
    world.db.commit()
    assert world.db.scalars(select(Dataset.name)).all() == ["B"]


def test_a_dataset_must_have_an_owner(db_session):
    db_session.add(Dataset(name="Orphan", original_filename="x.csv", row_count=1, column_count=1))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()