from pathlib import Path

from fastapi.testclient import TestClient

from engine.curriculum.lesson_id import encode_lesson_id, encode_tag
from serve_course import create_app

FIXTURE = Path(__file__).parent / "fixtures" / "curriculum_cache"


def _client(tmp_path) -> TestClient:
    app = create_app(
        cache_root=str(FIXTURE),
        curriculum_dir=str(tmp_path / "curriculum"),
        enable_ai_intro=False,
        serve_spa=False,
    )
    return TestClient(app)


def test_api_lesson_includes_sources_list(tmp_path):
    client = _client(tmp_path)
    modules = client.app.state.modules
    lesson = next(l for m in modules for l in m.lessons if m.tag == "估值")
    r = client.get(
        f"/api/lessons/{encode_lesson_id(lesson.lesson_id)}",
        params={"tag": encode_tag("估值")},
    )
    assert r.status_code == 200
    assert isinstance(r.json().get("sources"), list)


def test_api_logic_placeholder(tmp_path):
    client = _client(tmp_path)
    modules = client.app.state.modules
    lesson = next(l for m in modules for l in m.lessons if m.tag == "估值")
    r = client.get(
        f"/api/lessons/{encode_lesson_id(lesson.lesson_id)}/logic",
        params={"tag": encode_tag("估值")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["source"] in ("placeholder", "ai")
    assert "layers" in body
    assert "nodes" in body


def test_api_source_returns_window(tmp_path):
    client = _client(tmp_path)
    modules = client.app.state.modules
    lesson = next(l for m in modules for l in m.lessons if m.tag == "估值")
    excerpt = lesson.quote or lesson.opinion
    text_path = FIXTURE / lesson.book_title / "_chapters" / f"{lesson.chapter_index}.txt"
    text_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.write_text(f"前文。{excerpt}。后文。", encoding="utf-8")

    r = client.get(
        "/api/source",
        params={
            "book": lesson.book_title,
            "chapter": lesson.chapter_index or 1,
            "excerpt": excerpt,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert excerpt in body["text"]
    assert body.get("highlight") is not None
