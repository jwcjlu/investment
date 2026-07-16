from engine.cache import (
    save_chapter_note, load_chapter_note, has_chapter_note, write_markdown,
)
from engine.models import ChapterNote, OpinionEntry, BookSummary


def _note():
    return ChapterNote(
        chapter_index=3,
        chapter_title="第三章",
        core_points=["观点"],
        arguments=["论据"],
        actionables=["要点"],
        quotes=["金句"],
        opinions=[OpinionEntry(
            opinion="坚持纪律", chapter="第三章", tags=["投资纪律"],
            argument_summary="纪律带来一致性", actionability="原则", quote="纪律即自由",
        )],
        suggested_tags=[],
    )


def test_chapter_note_cache_roundtrip(tmp_path):
    book = "测试之书"
    note = _note()
    assert not has_chapter_note(book, 3, base=str(tmp_path))
    save_chapter_note(book, note, base=str(tmp_path))
    assert has_chapter_note(book, 3, base=str(tmp_path))
    loaded = load_chapter_note(book, 3, base=str(tmp_path))
    assert loaded == note


def test_write_markdown_creates_file(tmp_path):
    book = "测试之书"
    summary = BookSummary(
        book_title=book, author="作者", one_liner="一句话",
        core_theses=["核心1"], principles=["原则1"], open_questions=["疑问1"],
    )
    path = write_markdown(book, summary, [_note()], base=str(tmp_path))
    content = open(path, encoding="utf-8").read()
    assert "测试之书" in content
    assert "核心1" in content
    assert "坚持纪律" in content
