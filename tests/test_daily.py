from datetime import date

import config
from engine.curriculum.daily import add_more, load_or_create_daily, resolve_focus_tag
from engine.curriculum.models import Lesson, Module, ProgressState


def _lesson(lesson_id: str, actionability: str = "原则", tags=None) -> Lesson:
    return Lesson(
        lesson_id=lesson_id,
        book_title="测试书",
        chapter="第1章",
        chapter_index=1,
        opinion=f"观点-{lesson_id}",
        argument_summary="论据",
        actionability=actionability,
        quote="金句",
        tags=tags or ["估值"],
    )


def _modules(*specs) -> list[Module]:
    """specs: (tag, [(lesson_id, actionability), ...])"""
    return [
        Module(tag=tag, lessons=[_lesson(lid, act) for lid, act in lessons])
        for tag, lessons in specs
    ]


def test_resolve_focus_tag_prefers_preferred():
    modules = _modules(
        ("估值", [("v1", "原则")]),
        ("风险控制", [("r1", "原则")]),
    )
    progress = ProgressState(last_lesson_id="v1")
    assert resolve_focus_tag(modules, progress, preferred_tag="风险控制") == "风险控制"


def test_resolve_focus_tag_uses_fixed_tags_order_for_last_lesson():
    modules = _modules(
        ("估值", [("shared", "原则")]),
        ("风险控制", [("shared", "原则")]),
    )
    progress = ProgressState(last_lesson_id="shared")
    assert resolve_focus_tag(modules, progress) == "估值"


def test_resolve_focus_tag_first_module_with_unlearned_principles():
    modules = _modules(
        ("估值", [("v1", "原则")]),
        ("风险控制", [("r1", "原则"), ("r2", "可直接执行")]),
    )
    progress = ProgressState(completed=["v1"])
    assert resolve_focus_tag(modules, progress) == "风险控制"


def test_resolve_focus_tag_returns_none_when_all_principles_done():
    modules = _modules(
        ("估值", [("v1", "原则")]),
        ("风险控制", [("r1", "原则")]),
    )
    progress = ProgressState(completed=["v1", "r1"])
    assert resolve_focus_tag(modules, progress) is None


def test_load_or_create_daily_at_most_five_principles(tmp_path):
    lessons = [(f"p{i}", "原则") for i in range(8)]
    modules = _modules(("估值", lessons))
    progress = ProgressState()
    path = tmp_path / "daily.json"

    state = load_or_create_daily(str(path), modules, progress, today=date(2026, 7, 17))

    assert len(state["lesson_ids"]) == config.DAILY_LESSON_LIMIT
    assert state["lesson_ids"] == [f"p{i}" for i in range(5)]
    assert state["tag"] == "估值"
    assert state["extra_batches"] == 0
    assert state["date"] == "2026-07-17"


def test_load_or_create_daily_skips_completed_and_non_principles(tmp_path):
    modules = _modules(
        (
            "估值",
            [
                ("done", "原则"),
                ("exec", "可直接执行"),
                ("p1", "原则"),
                ("p2", "原则"),
            ],
        ),
    )
    progress = ProgressState(completed=["done"])
    path = tmp_path / "daily.json"

    state = load_or_create_daily(str(path), modules, progress, today=date(2026, 7, 17))

    assert state["lesson_ids"] == ["p1", "p2"]


def test_load_or_create_daily_cross_day_rebuilds_and_resets_extra_batches(tmp_path):
    modules = _modules(("估值", [(f"p{i}", "原则") for i in range(6)]))
    progress = ProgressState()
    path = tmp_path / "daily.json"
    path.write_text(
        '{"date":"2026-07-16","tag":"估值","lesson_ids":["old"],"extra_batches":2}',
        encoding="utf-8",
    )

    state = load_or_create_daily(str(path), modules, progress, today=date(2026, 7, 17))

    assert state["date"] == "2026-07-17"
    assert state["extra_batches"] == 0
    assert "old" not in state["lesson_ids"]
    assert len(state["lesson_ids"]) == 5


def test_load_or_create_daily_same_day_returns_cached(tmp_path):
    modules = _modules(("估值", [("p1", "原则")]))
    progress = ProgressState()
    path = tmp_path / "daily.json"
    path.write_text(
        '{"date":"2026-07-17","tag":"估值","lesson_ids":["p1"],"extra_batches":1}',
        encoding="utf-8",
    )

    state = load_or_create_daily(str(path), modules, progress, today=date(2026, 7, 17))

    assert state["lesson_ids"] == ["p1"]
    assert state["extra_batches"] == 1


def test_load_or_create_daily_corrupt_file_rebuilds(tmp_path):
    modules = _modules(("估值", [("p1", "原则")]))
    progress = ProgressState()
    path = tmp_path / "daily.json"
    path.write_text("{not json", encoding="utf-8")

    state = load_or_create_daily(str(path), modules, progress, today=date(2026, 7, 17))

    assert state["date"] == "2026-07-17"
    assert state["lesson_ids"] == ["p1"]
    assert state["extra_batches"] == 0


def test_add_more_appends_and_increments_extra_batches(tmp_path):
    lessons = [(f"p{i}", "原则") for i in range(12)]
    modules = _modules(("估值", lessons))
    progress = ProgressState()
    path = tmp_path / "daily.json"

    load_or_create_daily(str(path), modules, progress, today=date(2026, 7, 17))
    state, added = add_more(str(path), modules, progress)

    assert added == 5
    assert len(state["lesson_ids"]) == 10
    assert state["extra_batches"] == 1


def test_add_more_returns_zero_when_none_left(tmp_path):
    modules = _modules(("估值", [(f"p{i}", "原则") for i in range(7)]))
    progress = ProgressState()
    path = tmp_path / "daily.json"

    load_or_create_daily(str(path), modules, progress, today=date(2026, 7, 17))
    state, added = add_more(str(path), modules, progress)

    assert added == 2
    assert state["extra_batches"] == 1

    state, added = add_more(str(path), modules, progress)
    assert added == 0
    assert state["extra_batches"] == 1
