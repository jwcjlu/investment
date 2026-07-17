from __future__ import annotations
import os
import shutil
from typing import List

import mobi
from bs4 import BeautifulSoup

from engine.models import Chapter
from engine.parser import _split_by_headers, hard_split


def _parse_html_file(path: str) -> List[Chapter]:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        html = f.read()
    text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
    chapters = _split_by_headers(text)
    if not chapters:
        chapters = hard_split(text)
    return chapters


def parse_mobi(path: str) -> List[Chapter]:
    """解包未加密 MOBI，再按解出文件类型走 EPUB/PDF/HTML 解析。"""
    tempdir, extracted = mobi.extract(path)
    try:
        ext = os.path.splitext(extracted)[1].lower()
        if ext == ".epub":
            from engine.parser_epub import parse_epub
            return parse_epub(extracted)
        if ext == ".pdf":
            from engine.parser_pdf import parse_pdf
            return parse_pdf(extracted)
        if ext in (".html", ".htm", ".xhtml"):
            return _parse_html_file(extracted)
        if os.path.isfile(extracted):
            # KindleUnpack 偶发无标准扩展名，按 HTML 试读
            return _parse_html_file(extracted)
        raise ValueError(f"MOBI 解包后得到不支持的格式：{extracted}")
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)
