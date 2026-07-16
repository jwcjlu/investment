import os
import pytest
from engine.parser_epub import parse_epub

pytestmark = pytest.mark.skipif(
    not os.path.exists("tests/fixtures/sample.epub"),
    reason="先运行 tests/fixtures/make_sample_epub.py 生成 fixture",
)


def test_parse_epub_returns_chapters():
    chapters = parse_epub("tests/fixtures/sample.epub")
    assert len(chapters) >= 2
    joined = " ".join(c.text for c in chapters)
    assert "安全边际" in joined
    assert "风险控制" in joined
    # 标题应从 <h1> 或 spine 项提取，非空
    assert all(c.title.strip() for c in chapters)
    assert chapters[0].index == 1
