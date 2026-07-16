from __future__ import annotations
from typing import List
from ebooklib import epub, ITEM_DOCUMENT
from bs4 import BeautifulSoup
from engine.models import Chapter
from engine.parser import hard_split


def _html_to_title_text(html: str, fallback_title: str):
    soup = BeautifulSoup(html, "html.parser")
    h = soup.find(["h1", "h2", "title"])
    title = h.get_text(strip=True) if h and h.get_text(strip=True) else fallback_title
    text = soup.get_text("\n", strip=True)
    return title, text


def parse_epub(path: str) -> List[Chapter]:
    book = epub.read_epub(path)
    chapters: List[Chapter] = []
    order = 0
    for item in book.get_items_of_type(ITEM_DOCUMENT):
        html = item.get_content().decode("utf-8", errors="ignore")
        title, text = _html_to_title_text(html, fallback_title=item.get_name())
        if not text.strip():
            continue
        order += 1
        chapters.append(Chapter(index=order, title=title, text=text))

    # 兜底：若只解析出 1 个巨大文档，按字数硬切
    if len(chapters) == 1:
        chapters = hard_split(chapters[0].text)
    return chapters
