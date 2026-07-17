import os
from unittest.mock import patch

import pytest

from engine.parser import parse_book


def test_parse_mobi_via_extracted_epub(tmp_path):
    """mobi.extract 解出 EPUB 时，应复用 EPUB 解析得到多章。"""
    epub_path = os.path.abspath("tests/fixtures/sample.epub")
    if not os.path.exists(epub_path):
        pytest.skip("先运行 tests/fixtures/make_sample_epub.py 生成 fixture")

    mobi_path = tmp_path / "sample.mobi"
    mobi_path.write_bytes(b"fake-mobi")  # 内容由 mock 接管，不真正解析

    with patch("engine.parser_mobi.mobi.extract", return_value=(str(tmp_path), epub_path)):
        from engine.parser_mobi import parse_mobi

        chapters = parse_mobi(str(mobi_path))

    assert len(chapters) >= 2
    joined = " ".join(c.text for c in chapters)
    assert "安全边际" in joined
    assert "风险控制" in joined
    assert chapters[0].index == 1


def test_parse_mobi_via_extracted_html(tmp_path):
    """mobi.extract 解出单文件 HTML 时，应按章节标题或硬切分章。"""
    html_path = tmp_path / "book.html"
    html_path.write_text(
        "<html><body>"
        "<h1>第一章 开端</h1><p>安全边际是价值投资的核心。</p>"
        "<h1>第二章 进阶</h1><p>风险控制决定长期生存。</p>"
        "</body></html>",
        encoding="utf-8",
    )
    mobi_path = tmp_path / "sample.mobi"
    mobi_path.write_bytes(b"fake-mobi")

    with patch("engine.parser_mobi.mobi.extract", return_value=(str(tmp_path), str(html_path))):
        from engine.parser_mobi import parse_mobi

        chapters = parse_mobi(str(mobi_path))

    assert len(chapters) >= 2
    joined = " ".join(c.text for c in chapters)
    assert "安全边际" in joined
    assert "风险控制" in joined


def test_parse_book_dispatches_mobi(tmp_path):
    epub_path = os.path.abspath("tests/fixtures/sample.epub")
    if not os.path.exists(epub_path):
        pytest.skip("先运行 tests/fixtures/make_sample_epub.py 生成 fixture")

    mobi_path = tmp_path / "dispatch.mobi"
    mobi_path.write_bytes(b"fake-mobi")

    with patch("engine.parser_mobi.mobi.extract", return_value=(str(tmp_path), epub_path)):
        chapters = parse_book(str(mobi_path))

    assert len(chapters) >= 2
    assert "安全边际" in chapters[0].text or any("安全边际" in c.text for c in chapters)
