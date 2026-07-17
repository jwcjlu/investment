from pathlib import Path

from fastapi.testclient import TestClient

from serve_course import create_app
from engine.curriculum.lesson_id import encode_lesson_id, encode_tag

FIXTURE = Path(__file__).parent / "fixtures" / "curriculum_cache"


def test_index_ok_with_fixture_cache(tmp_path):
    app = create_app(
        cache_root=str(FIXTURE),
        curriculum_dir=str(tmp_path / "curriculum"),
        enable_ai_intro=False,
    )
    r = TestClient(app).get("/")
    assert r.status_code == 200
    assert "估值" in r.text or "学习" in r.text


def test_empty_cache_friendly_message(tmp_path):
    empty = tmp_path / "cache"
    empty.mkdir()
    app = create_app(
        cache_root=str(empty),
        curriculum_dir=str(tmp_path / "cur"),
        enable_ai_intro=False,
    )
    r = TestClient(app).get("/")
    assert r.status_code == 200
    assert "read_book" in r.text or "精读" in r.text


def test_module_page_ok_with_encoded_tag(tmp_path):
    app = create_app(
        cache_root=str(FIXTURE),
        curriculum_dir=str(tmp_path / "curriculum"),
        enable_ai_intro=False,
    )
    r = TestClient(app).get(f"/module/{encode_tag('估值')}")
    assert r.status_code == 200
    assert "估值很重要" in r.text


def test_module_page_ok_with_slash_in_tag(tmp_path):
    """标签含 '/'（如 护城河/竞争优势）时，encode_tag 会产出 %2F；
    真实 ASGI 服务器在路由匹配前会把 %2F 解码为 '/'，
    因此路由必须能匹配含 '/' 的路径段，否则 404。"""
    app = create_app(
        cache_root=str(FIXTURE),
        curriculum_dir=str(tmp_path / "curriculum"),
        enable_ai_intro=False,
    )
    tag = "护城河/竞争优势"
    r = TestClient(app).get(f"/module/{encode_tag(tag)}")
    assert r.status_code == 200
    assert "护城河决定长期回报" in r.text


def test_homepage_links_to_slash_tag_module(tmp_path):
    app = create_app(
        cache_root=str(FIXTURE),
        curriculum_dir=str(tmp_path / "curriculum"),
        enable_ai_intro=False,
    )
    client = TestClient(app)
    tag = "护城河/竞争优势"
    encoded = encode_tag(tag)

    index_html = client.get("/").text
    assert f"/module/{encoded}" in index_html

    r = client.get(f"/module/{encoded}")
    assert r.status_code == 200


def test_lesson_page_ok_and_progress_roundtrip(tmp_path):
    app = create_app(
        cache_root=str(FIXTURE),
        curriculum_dir=str(tmp_path / "curriculum"),
        enable_ai_intro=False,
    )
    client = TestClient(app)

    modules = app.state.modules
    tag = "估值"
    module = next(m for m in modules if m.tag == tag)
    lesson = module.lessons[0]

    r = client.get(f"/lesson/{encode_lesson_id(lesson.lesson_id)}?tag={encode_tag(tag)}")
    assert r.status_code == 200
    assert lesson.opinion in r.text

    r = client.post("/api/progress/complete", json={"lesson_id": lesson.lesson_id})
    assert r.status_code in (200, 204)

    r = client.get("/api/progress")
    assert r.status_code == 200
    data = r.json()
    assert lesson.lesson_id in data["completed"]
    assert data["last_lesson_id"] == lesson.lesson_id

    # 首页应显示「继续上次」链接
    r = client.get("/")
    assert r.status_code == 200
    assert "继续" in r.text
