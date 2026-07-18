from engine.curriculum.logic_writer import (
    generate_ai_logic,
    get_or_create_logic,
    placeholder_logic,
)
from engine.curriculum.models import Lesson
from engine.models import ChapterNote, SourceRef


def _lesson(**kwargs):
    base = dict(
        lesson_id="book|第1章|原则",
        book_title="书",
        chapter="第1章",
        chapter_index=1,
        opinion="价值创造看 ROIC 与成本之差",
        argument_summary="差额决定价值",
        actionability="原则",
        quote="回报率与成本之差",
        tags=["估值"],
        sources=[],
    )
    base.update(kwargs)
    return Lesson(**base)


def test_placeholder_logic_layers_from_lesson_and_note():
    lesson = _lesson(
        sources=[
            SourceRef(
                book_title="书",
                chapter_index=1,
                excerpt="回报率与成本之差",
            )
        ]
    )
    note = ChapterNote(
        chapter_index=1,
        chapter_title="第1章",
        core_points=["WACC 是及格线", "会计利润不等于经济利润"],
        arguments=[],
        actionables=[],
        quotes=[],
    )
    logic = placeholder_logic(lesson, note)
    assert logic.source == "placeholder"
    assert logic.edges == []
    assert logic.layers[0].level == 1
    assert any(n.label == lesson.opinion for n in logic.nodes)
    l1 = next(n for n in logic.nodes if n.label == lesson.opinion)
    assert l1.ungrounded is False
    assert l1.sources


def test_get_or_create_uses_cache(tmp_path, monkeypatch):
    lesson = _lesson()
    note = ChapterNote(
        chapter_index=1,
        chapter_title="第1章",
        core_points=["a"],
        arguments=[],
        actionables=[],
        quotes=[],
    )
    calls = {"n": 0}

    def boom(*a, **k):
        calls["n"] += 1
        raise RuntimeError("should not be called when cache hit")

    monkeypatch.setattr("engine.curriculum.logic_writer.generate_ai_logic", boom)
    logic_dir = tmp_path / "logic"
    first = get_or_create_logic(lesson, str(logic_dir), note=note, use_ai=False)
    second = get_or_create_logic(lesson, str(logic_dir), note=note, use_ai=True)
    assert first.to_dict() == second.to_dict()
    assert calls["n"] == 0


def test_generate_ai_logic_assigns_stable_ids(monkeypatch):
    lesson = _lesson()

    monkeypatch.setattr("engine.curriculum.logic_writer.make_client", lambda: object())
    monkeypatch.setattr(
        "engine.curriculum.logic_writer.create_structured",
        lambda *a, **k: {
            "layers": [{"level": 1, "title": "结论", "labels": ["价值创造"]}],
            "nodes": [
                {
                    "label": "价值创造",
                    "kind": "claim",
                    "aliases": [],
                    "excerpt": "回报率与成本之差",
                },
                {
                    "label": "ROIC",
                    "kind": "metric",
                    "aliases": [],
                    "excerpt": "投资资本回报率",
                },
            ],
            "edges": [
                {
                    "from_label": "ROIC",
                    "to_label": "价值创造",
                    "rel": "causes",
                    "excerpt": "回报率与成本之差",
                }
            ],
        },
    )
    logic = generate_ai_logic(lesson, None)
    assert logic.source == "ai"
    assert all(n.node_id.startswith("n_") for n in logic.nodes)
    assert all(e.edge_id.startswith("e_") for e in logic.edges)
