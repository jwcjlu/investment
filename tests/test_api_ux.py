from pathlib import Path

from fastapi.testclient import TestClient

from serve_course import create_app
from engine.curriculum.lesson_id import encode_lesson_id, encode_tag
from engine.curriculum.quiz_writer import placeholder_quiz, save_quiz

FIXTURE = Path(__file__).parent / "fixtures" / "curriculum_cache"


def _client(tmp_path, **kwargs) -> TestClient:
    kwargs.setdefault("serve_spa", False)
    app = create_app(
        cache_root=str(FIXTURE),
        curriculum_dir=str(tmp_path / "curriculum"),
        enable_ai_intro=False,
        **kwargs,
    )
    return TestClient(app)


def test_api_modules_lists_tags_and_progress(tmp_path):
    client = _client(tmp_path)
    r = client.get("/api/modules")
    assert r.status_code == 200
    data = r.json()
    tags = [m["tag"] for m in data["modules"]]
    assert "估值" in tags
    assert "护城河/竞争优势" in tags
    assert data["completed_count"] == 0
    assert data["continue_lesson"] is None
    for m in data["modules"]:
        assert m["encoded_tag"] == encode_tag(m["tag"])


def test_api_module_detail_with_slash_tag(tmp_path):
    client = _client(tmp_path)
    tag = "护城河/竞争优势"
    encoded = encode_tag(tag)

    r = client.get(f"/api/modules/{encoded}")
    assert r.status_code == 200
    data = r.json()
    assert data["tag"] == tag
    assert data["encoded_tag"] == encoded
    assert data["intro"]["goals"]
    assert len(data["lessons"]) == 1
    assert data["lessons"][0]["opinion"] == "护城河决定长期回报"


def test_api_module_detail_missing_tag_404(tmp_path):
    client = _client(tmp_path)
    r = client.get(f"/api/modules/{encode_tag('不存在的标签')}")
    assert r.status_code == 404


def test_api_lesson_detail_requires_tag_and_returns_next_lesson_fields(tmp_path):
    client = _client(tmp_path)
    tag = "估值"
    encoded_tag = encode_tag(tag)
    module_detail = client.get(f"/api/modules/{encoded_tag}").json()
    lesson = module_detail["lessons"][0]

    r = client.get(f"/api/lessons/{lesson['encoded_id']}?tag={encoded_tag}")
    assert r.status_code == 200
    data = r.json()
    assert data["lesson_id"] == lesson["lesson_id"]
    assert data["encoded_id"] == lesson["encoded_id"]
    assert data["tag"] == tag
    assert data["encoded_tag"] == encoded_tag
    assert data["opinion"] == "估值很重要"
    assert data["argument_summary"]
    assert data["quote"]
    assert data["chapter_note"] is None
    # fixture 估值 模块只有一课，无下一课
    assert data["next_lesson_id"] is None
    assert data["next_encoded_id"] is None


def test_api_lesson_detail_expand_returns_chapter_note(tmp_path):
    client = _client(tmp_path)
    tag = "估值"
    encoded_tag = encode_tag(tag)
    module_detail = client.get(f"/api/modules/{encoded_tag}").json()
    lesson = module_detail["lessons"][0]

    r = client.get(
        f"/api/lessons/{lesson['encoded_id']}?tag={encoded_tag}&expand=1"
    )
    assert r.status_code == 200
    data = r.json()
    assert data["chapter_note"] is not None
    assert data["chapter_note"]["chapter_title"] == "第1章"


def test_api_progress_roundtrip(tmp_path):
    client = _client(tmp_path)
    tag = "估值"
    module_detail = client.get(f"/api/modules/{encode_tag(tag)}").json()
    lesson_id = module_detail["lessons"][0]["lesson_id"]

    r = client.post("/api/progress", json={"lesson_id": lesson_id})
    assert r.status_code == 200

    r = client.get("/api/progress")
    assert r.status_code == 200
    data = r.json()
    assert lesson_id in data["completed"]
    assert data["last_lesson_id"] == lesson_id


def test_api_daily_defaults_to_first_focus_tag(tmp_path):
    client = _client(tmp_path)
    r = client.get("/api/daily")
    assert r.status_code == 200
    data = r.json()
    assert len(data["lesson_ids"]) <= 5
    assert data["tag"] == "估值"
    assert data["extra_batches"] == 0
    assert data["lessons"]
    assert data["lessons"][0]["opinion"] == "估值很重要"


def test_api_daily_with_explicit_tag(tmp_path):
    client = _client(tmp_path)
    tag = "护城河/竞争优势"
    r = client.get(f"/api/daily?tag={encode_tag(tag)}")
    assert r.status_code == 200
    data = r.json()
    assert data["tag"] == tag
    assert data["encoded_tag"] == encode_tag(tag)


def test_api_daily_more_returns_zero_when_nothing_left(tmp_path):
    client = _client(tmp_path)
    client.get("/api/daily")  # 初始化今日清单（估值 模块仅 1 则原则课，已全部入清单）

    r = client.post("/api/daily/more")
    assert r.status_code == 200
    data = r.json()
    assert data["added"] == 0
    assert data["tag"] == "估值"


def test_api_quiz_by_tag_returns_placeholder_for_slash_tag(tmp_path):
    client = _client(tmp_path)
    tag = "护城河/竞争优势"
    r = client.get(f"/api/quiz?tag={encode_tag(tag)}")
    assert r.status_code == 200
    data = r.json()
    assert data["tag"] == tag
    assert data["source"] == "placeholder"
    assert len(data["questions"]) >= 2
    assert data["encoded_tag"] == encode_tag(tag)


def test_api_quiz_daily_uses_focus_tag_quiz(tmp_path):
    client = _client(tmp_path)
    client.get("/api/daily")  # 建立 daily.json，焦点为 估值

    r = client.get("/api/quiz?daily=1")
    assert r.status_code == 200
    data = r.json()
    assert data["tag"] == "估值"


def test_api_quiz_missing_params_400(tmp_path):
    client = _client(tmp_path)
    r = client.get("/api/quiz")
    assert r.status_code == 400


def test_api_quiz_force_rebuilds_with_ai(tmp_path, monkeypatch):
    curriculum_dir = tmp_path / "curriculum"
    quizzes_dir = curriculum_dir / "quizzes"
    quizzes_dir.mkdir(parents=True)

    tag = "估值"

    # 预置占位缓存
    from engine.curriculum.models import Lesson, Module

    fake_module = Module(
        tag=tag,
        lessons=[
            Lesson("id1", "书A", "章1", 1, "低估值买入", "论据A", "原则", "金句A", [tag]),
        ],
    )
    save_quiz(placeholder_quiz(fake_module), str(quizzes_dir))

    ai_quiz = {
        "tag": tag,
        "source": "ai",
        "questions": [
            {
                "id": "q1",
                "stem": "AI 题1",
                "options": ["A", "B", "C", "D"],
                "answer_index": 0,
                "explanation": "解析1",
            },
            {
                "id": "q2",
                "stem": "AI 题2",
                "options": ["A", "B", "C", "D"],
                "answer_index": 1,
                "explanation": "解析2",
            },
        ],
    }
    calls = {"n": 0}

    def fake_ai(module):
        calls["n"] += 1
        return ai_quiz

    monkeypatch.setattr("engine.curriculum.quiz_writer.generate_ai_quiz", fake_ai)

    app = create_app(
        cache_root=str(FIXTURE),
        curriculum_dir=str(curriculum_dir),
        enable_ai_intro=True,
        serve_spa=False,
    )
    client = TestClient(app)

    # 未 force：应命中占位缓存，不调用 AI
    r = client.get(f"/api/quiz?tag={encode_tag(tag)}")
    assert r.status_code == 200
    assert r.json()["source"] == "placeholder"
    assert calls["n"] == 0

    # force=1：绕过缓存，调用（已 mock 的）AI
    r = client.get(f"/api/quiz?tag={encode_tag(tag)}&force=1")
    assert r.status_code == 200
    data = r.json()
    assert data["source"] == "ai"
    assert calls["n"] == 1


def test_api_quiz_submit_grades_answers(tmp_path):
    client = _client(tmp_path)
    tag = "估值"
    quiz = client.get(f"/api/quiz?tag={encode_tag(tag)}").json()
    q1 = quiz["questions"][0]

    r = client.post(
        "/api/quiz/submit",
        json={"tag": tag, "answers": {q1["id"]: q1["answer_index"]}},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["score"] == 1
    assert data["details"][0]["id"] == q1["id"]
    assert data["details"][0]["correct"] is True


def test_api_quiz_submit_unknown_tag_404(tmp_path):
    client = _client(tmp_path)
    r = client.post(
        "/api/quiz/submit",
        json={"tag": "从未获取过测验的标签", "answers": {}},
    )
    assert r.status_code == 404
