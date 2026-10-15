import pytest
from fastapi.testclient import TestClient
import re
from pathlib import Path

from app.main import app

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"

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

def test_every_imported_js_module_exists_and_is_served(client):
    for js_file in (FRONTEND / "js").glob("*.js"):
        for target in re.findall(r'from "\./([\w-]+\.js)"', js_file.read_text(encoding="utf-8")):
            assert (FRONTEND / "js" / target).exists(), f"{js_file.name} imports missing {target}"
            assert client.get(f"/js/{target}").status_code == 200