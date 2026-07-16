from __future__ import annotations
from typing import List
from pypdf import PdfReader
from engine.models import Chapter
from engine.parser import _split_by_headers, hard_split


def parse_pdf(path: str) -> List[Chapter]:
    reader = PdfReader(path)
    full_text = "\n".join((page.extract_text() or "") for page in reader.pages)

    # 先尝试按章节标题切；失败则按字数硬切
    chapters = _split_by_headers(full_text)
    if not chapters:
        chapters = hard_split(full_text)
    return chapters
