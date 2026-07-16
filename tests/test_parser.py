from engine.parser import parse_txt, hard_split, parse_book
from engine.models import Chapter


def test_parse_txt_splits_by_chapter_headers():
    chapters = parse_txt("tests/fixtures/sample.txt")
    assert len(chapters) == 3
    assert chapters[0].index == 1
    assert "第一章" in chapters[0].title
    assert "安全边际" in chapters[0].text
    assert chapters[1].index == 2
    assert "风险控制" in chapters[1].text


def test_hard_split_chunks_by_size():
    text = "字" * 25000
    chapters = hard_split(text, chunk_chars=8000)
    assert len(chapters) == 4  # 25000/8000 向上取整
    assert all(isinstance(c, Chapter) for c in chapters)
    assert chapters[0].index == 1
    assert "段" in chapters[0].title  # 硬切段标题含"段"


def test_parse_book_dispatches_on_extension():
    chapters = parse_book("tests/fixtures/sample.txt")
    assert len(chapters) == 3
