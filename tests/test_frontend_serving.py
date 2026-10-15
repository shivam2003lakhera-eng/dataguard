import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def test_root_serves_the_frontend_page(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "DataGuard" in r.text


def test_static_assets_are_served(client):
    assert client.get("/css/styles.css").status_code == 200
    assert client.get("/js/api.js").status_code == 200


def test_api_routes_still_work_with_static_mount(client):
    assert client.get("/api/v1/nope").status_code == 404
    assert client.get("/docs").status_code == 200