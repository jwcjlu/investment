from engine.curriculum.models import Lesson, Module, ModuleIntro
from engine.curriculum.intro_writer import placeholder_intro, load_intro, save_intro, get_or_create_intro


def _mod():
    return Module(
        tag="估值",
        lessons=[
            Lesson("id", "书A", "章1", 1, "观点", "论据", "原则", "金句", ["估值"]),
        ],
    )


def test_placeholder_intro_has_tag_and_source():
    intro = placeholder_intro(_mod())
    assert intro.tag == "估值"
    assert intro.source == "placeholder"
    assert intro.goals


def test_save_load_roundtrip(tmp_path):
    intro = placeholder_intro(_mod())
    save_intro(intro, str(tmp_path))
    loaded = load_intro("估值", str(tmp_path))
    assert loaded.goals == intro.goals


def test_get_or_create_uses_cache_without_ai(tmp_path, monkeypatch):
    calls = {"n": 0}

    def boom(*a, **k):
        calls["n"] += 1
        raise AssertionError("should not call AI when cache exists")

    monkeypatch.setattr("engine.curriculum.intro_writer.generate_ai_intro", boom)
    save_intro(placeholder_intro(_mod()), str(tmp_path))
    intro = get_or_create_intro(_mod(), str(tmp_path), use_ai=True)
    assert intro.source in ("placeholder", "ai")
    assert calls["n"] == 0
