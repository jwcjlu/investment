"""SPA 托管：存在 static/spa 时走 FileResponse，并保留 /api。"""

from pathlib import Path

from fastapi.testclient import TestClient

from serve_course import create_app

FIXTURE = Path(__file__).parent / "fixtures" / "curriculum_cache"


def test_spa_root_and_fallback_when_built(tmp_path, monkeypatch):
    spa = tmp_path / "spa"
    spa.mkdir()
    (spa / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    assets = spa / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log(1)", encoding="utf-8")

    monkeypatch.setattr("serve_course.SPA_DIR", str(spa))

    app = create_app(
        cache_root=str(FIXTURE),
        curriculum_dir=str(tmp_path / "curriculum"),
        enable_ai_intro=False,
        serve_spa=True,
    )
    client = TestClient(app)

    r = client.get("/")
    assert r.status_code == 200
    assert "spa" in r.text

    r = client.get("/module/anything")
    assert r.status_code == 200
    assert "spa" in r.text

    r = client.get("/api/modules")
    assert r.status_code == 200
    assert "modules" in r.json()


def test_spa_missing_returns_503(tmp_path, monkeypatch):
    missing = tmp_path / "no-spa"
    missing.mkdir()
    monkeypatch.setattr("serve_course.SPA_DIR", str(missing))

    app = create_app(
        cache_root=str(FIXTURE),
        curriculum_dir=str(tmp_path / "curriculum"),
        enable_ai_intro=False,
        serve_spa=True,
    )
    r = TestClient(app).get("/")
    assert r.status_code == 503
