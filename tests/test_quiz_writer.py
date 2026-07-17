from engine.curriculum.models import Lesson, Module
from engine.curriculum.quiz_writer import (
    placeholder_quiz,
    save_quiz,
    load_quiz,
    get_or_create_quiz,
    grade,
)


def _mod(tag: str = "估值"):
    return Module(
        tag=tag,
        lessons=[
            Lesson("id1", "书A", "章1", 1, "低估值买入", "论据A", "原则", "金句A", [tag]),
            Lesson("id2", "书B", "章2", 2, "安全边际", "论据B", "原则", "金句B", [tag]),
        ],
    )


def test_placeholder_quiz_has_2_to_3_questions():
    quiz = placeholder_quiz(_mod())
    assert quiz["tag"] == "估值"
    assert quiz["source"] == "placeholder"
    assert 2 <= len(quiz["questions"]) <= 3
    q = quiz["questions"][0]
    assert q["id"]
    assert q["stem"]
    assert len(q["options"]) == 4
    assert 0 <= q["answer_index"] <= 3
    assert q["explanation"]


def test_save_load_roundtrip(tmp_path):
    quiz = placeholder_quiz(_mod())
    save_quiz(quiz, str(tmp_path))
    loaded = load_quiz("估值", str(tmp_path))
    assert loaded["questions"] == quiz["questions"]
    assert loaded["source"] == "placeholder"


def test_get_or_create_uses_cache_without_ai(tmp_path, monkeypatch):
    calls = {"n": 0}

    def boom(*a, **k):
        calls["n"] += 1
        raise AssertionError("should not call AI when cache exists")

    monkeypatch.setattr("engine.curriculum.quiz_writer.generate_ai_quiz", boom)
    save_quiz(placeholder_quiz(_mod()), str(tmp_path))
    quiz = get_or_create_quiz(_mod(), str(tmp_path), use_ai=True)
    assert quiz["source"] in ("placeholder", "ai")
    assert calls["n"] == 0


def test_grade_submission():
    quiz = placeholder_quiz(_mod())
    q1 = quiz["questions"][0]
    q2 = quiz["questions"][1]
    result = grade(quiz, {
        q1["id"]: q1["answer_index"],
        q2["id"]: (q2["answer_index"] + 1) % 4,
    })
    assert result["score"] == 1
    assert len(result["details"]) == 2
    by_id = {d["id"]: d for d in result["details"]}
    assert by_id[q1["id"]]["correct"] is True
    assert by_id[q2["id"]]["correct"] is False
    assert by_id[q1["id"]]["explanation"]
