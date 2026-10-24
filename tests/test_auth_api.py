from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from app.api.routes.auth import login_limiter
from app.core.config import get_settings
from app.core.security import hash_token
from app.db.session import get_db
from app.main import app
from app.models import User, UserSession

API = "/api/v1"
COOKIE = "dataguard_session"
PASSWORD = "correct horse 9"


@pytest.fixture
def client(db_session):
    def override():
        yield db_session

    app.dependency_overrides[get_db] = override
    login_limiter.clear()
    yield new_client()
    login_limiter.clear()
    app.dependency_overrides.clear()


def new_client() -> TestClient:
    """A browser with its own, empty cookie jar."""
    return TestClient(app, raise_server_exceptions=False)


def register(client, email="alice@example.com", password=PASSWORD):
    return client.post(f"{API}/auth/register", json={"email": email, "password": password})


def login(client, email="alice@example.com", password=PASSWORD):
    return client.post(f"{API}/auth/login", json={"email": email, "password": password})


def code(response) -> str:
    return response.json()["error"]["code"]


def cookie_attributes(response) -> list[str]:
    header = response.headers["set-cookie"]
    return [part.strip().lower() for part in header.split(";")[1:]]


def count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


# ---------- Register ----------

def test_register_creates_account_and_logs_in(client):
    r = register(client)
    assert r.status_code == 201
    assert r.json()["email"] == "alice@example.com"
    assert client.cookies.get(COOKIE) is not None

    me = client.get(f"{API}/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"


def test_register_normalizes_email(client, db_session):
    r = register(client, "  Alice@Example.COM ")
    assert r.status_code == 201
    assert r.json()["email"] == "alice@example.com"
    assert db_session.scalars(select(User)).one().email == "alice@example.com"


def test_register_response_never_contains_password_data(client):
    r = register(client)
    assert set(r.json()) == {"id", "email", "created_at"}
    assert PASSWORD not in r.text and "scrypt" not in r.text


def test_register_duplicate_email_is_rejected_ignoring_case(client):
    register(client)
    r = register(new_client(), "ALICE@example.com")
    assert r.status_code == 409
    assert code(r) == "conflict"


@pytest.mark.parametrize("email", ["not-an-email", "a@b", "@x.com", "a b@x.com", ""])
def test_register_rejects_invalid_email(client, email):
    r = register(client, email)
    assert r.status_code == 422
    assert code(r) == "validation_error"


@pytest.mark.parametrize("password", ["short77", "x" * 129])
def test_register_rejects_bad_password_length(client, password):
    r = register(client, password=password)
    assert r.status_code == 422
    assert code(r) == "validation_error"


def test_register_rejects_unknown_fields(client):
    r = client.post(
        f"{API}/auth/register",
        json={"email": "a@example.com", "password": PASSWORD, "is_admin": True},
    )
    assert r.status_code == 422


def test_password_is_stored_hashed(client, db_session):
    register(client)
    stored = db_session.scalars(select(User)).one().password_hash
    assert stored.startswith("scrypt$")
    assert PASSWORD not in stored


# ---------- Login ----------

def test_login_success_sets_cookie(client):
    register(client)
    browser = new_client()
    r = login(browser)
    assert r.status_code == 200
    assert browser.cookies.get(COOKIE) is not None
    assert browser.get(f"{API}/auth/me").json()["email"] == "alice@example.com"


def test_login_wrong_password_is_generic_and_sets_no_cookie(client):
    register(client)
    r = login(new_client(), password="wrong password 1")
    assert r.status_code == 401
    assert code(r) == "invalid_credentials"
    assert r.json()["error"]["message"] == "Incorrect email or password."
    assert "set-cookie" not in r.headers


def test_unknown_email_looks_identical_to_wrong_password(client):
    register(client)
    wrong_password = login(new_client(), password="wrong password 1")
    unknown_email = login(new_client(), email="nobody@example.com")
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


# ---------- Who am I ----------

def test_me_without_login_is_401(client):
    r = client.get(f"{API}/auth/me")
    assert r.status_code == 401
    assert code(r) == "not_authenticated"


def test_me_with_a_made_up_cookie_is_401(client):
    client.cookies.set(COOKIE, "garbage-token")
    assert client.get(f"{API}/auth/me").status_code == 401


def test_expired_session_is_rejected(client, db_session):
    register(client)
    db_session.execute(
        update(UserSession).values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    db_session.commit()
    assert client.get(f"{API}/auth/me").status_code == 401


def test_health_stays_public(client):
    assert new_client().get(f"{API}/health").status_code == 200


# ---------- Logout ----------

def test_logout_ends_the_session_on_the_server(client, db_session):
    register(client)
    token = client.cookies.get(COOKIE)

    assert client.post(f"{API}/auth/logout").status_code == 204
    assert client.get(f"{API}/auth/me").status_code == 401
    assert count(db_session, UserSession) == 0

    thief = new_client()  # replaying the old cookie must not work
    thief.cookies.set(COOKIE, token)
    assert thief.get(f"{API}/auth/me").status_code == 401


def test_logout_without_a_session_is_fine(client):
    assert client.post(f"{API}/auth/logout").status_code == 204


def test_logout_only_ends_the_current_session(client):
    register(client)
    other = new_client()
    login(other)

    client.post(f"{API}/auth/logout")
    assert other.get(f"{API}/auth/me").status_code == 200


# ---------- Tokens and cookies ----------

def test_only_the_token_hash_is_stored(client, db_session):
    register(client)
    token = client.cookies.get(COOKIE)
    stored = db_session.scalars(select(UserSession)).one().token_hash
    assert stored == hash_token(token)
    assert stored != token


def test_cookie_flags(client):
    attrs = cookie_attributes(register(client))
    assert "httponly" in attrs
    assert "samesite=lax" in attrs
    assert "path=/" in attrs
    assert any(a.startswith("max-age=") for a in attrs)
    assert "secure" not in attrs


def test_cookie_is_secure_when_configured(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "cookie_secure", True)
    assert "secure" in cookie_attributes(register(client))


# ---------- Registration switch ----------

def test_registration_can_be_closed(client, db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "allow_registration", False)
    r = register(client)
    assert r.status_code == 403
    assert code(r) == "registration_closed"
    assert count(db_session, User) == 0


def test_existing_users_can_still_log_in_when_registration_is_closed(client, monkeypatch):
    register(client)
    monkeypatch.setattr(get_settings(), "allow_registration", False)
    assert login(new_client()).status_code == 200


# ---------- Rate limit ----------

def test_five_failures_block_further_attempts(client):
    register(client)
    browser = new_client()
    for _ in range(5):
        assert login(browser, password="wrong password 1").status_code == 401

    r = login(browser)  # even the correct password is refused now
    assert r.status_code == 429
    assert code(r) == "too_many_attempts"


def test_blocking_one_email_does_not_block_another(client):
    register(client)
    register(new_client(), "bob@example.com")
    browser = new_client()
    for _ in range(5):
        login(browser, password="wrong password 1")

    assert login(new_client(), "bob@example.com").status_code == 200


def test_a_successful_login_resets_the_failure_count(client):
    register(client)
    browser = new_client()
    for _ in range(4):
        login(browser, password="wrong password 1")
    assert login(browser).status_code == 200

    for _ in range(4):
        assert login(browser, password="wrong password 1").status_code == 401