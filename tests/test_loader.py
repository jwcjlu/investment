from pathlib import Path
from engine.curriculum.loader import load_catalog_from_cache


FIXTURE = Path(__file__).parent / "fixtures" / "curriculum_cache"


def test_load_catalog_reads_opinions():
    items, notes_index, warnings = load_catalog_from_cache(str(FIXTURE))
    assert any(i.book_title == "样例书" for i in items)
    assert any("估值" in i.opinion.tags for i in items)
    key = ("样例书", 1)
    assert key in notes_index


def test_load_skips_corrupt_json():
    items, notes_index, warnings = load_catalog_from_cache(str(FIXTURE))
    assert any("坏书" in w or "第1章" in w for w in warnings)
    assert not any(i.book_title == "坏书" for i in items)
