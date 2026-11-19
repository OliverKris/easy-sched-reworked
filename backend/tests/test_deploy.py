"""Production wiring: config endpoint, upload size limit, and serving the built frontend."""
import importlib.util
import sys
from pathlib import Path

from fastapi.testclient import TestClient

import api

BACKEND = Path(__file__).resolve().parent.parent


def test_config_reports_demo_mode():
    with TestClient(api.app) as client:
        body = client.get("/api/config").json()
    assert body == {"demo_mode": api.DEMO_MODE}


def test_oversized_request_is_rejected():
    with TestClient(api.app) as client:
        res = client.post(
            "/api/workspaces/import",
            content=b"x",
            headers={"Content-Length": str(api.MAX_BODY_BYTES + 1), "X-Client-Id": "size-test"},
        )
    assert res.status_code == 413


def _load_api_with_dist(monkeypatch, dist: Path):
    """Import a fresh copy of api.py that sees EASY_SCHED_FRONTEND_DIST=dist."""
    monkeypatch.setenv("EASY_SCHED_FRONTEND_DIST", str(dist))
    spec = importlib.util.spec_from_file_location("api_with_frontend", BACKEND / "api.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["api_with_frontend"] = module
    spec.loader.exec_module(module)
    return module


def test_serves_built_frontend_and_spa_routes(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>Easy-Sched</title>")
    (tmp_path / "assets" / "app.js").write_text("console.log('hi')")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    (tmp_path.parent / "secret.txt").write_text("nope")

    mod = _load_api_with_dist(monkeypatch, tmp_path)
    with TestClient(mod.app) as client:
        assert "Easy-Sched" in client.get("/").text
        assert "Easy-Sched" in client.get("/assign").text          # client-side route
        assert client.get("/assets/app.js").text == "console.log('hi')"
        assert client.get("/favicon.svg").text == "<svg/>"
        assert client.get("/health").json() == {"status": "ok"}     # API still wins
        assert client.get("/api/nope").status_code == 404           # unknown API path isn't the app
        assert "nope" not in client.get("/../secret.txt").text      # no escaping the build folder


def test_no_frontend_routes_without_a_build(tmp_path, monkeypatch):
    mod = _load_api_with_dist(monkeypatch, tmp_path / "missing")
    with TestClient(mod.app) as client:
        assert client.get("/assign").status_code == 404
