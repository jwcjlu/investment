from __future__ import annotations
import os
import re
import math
from typing import List
from engine.models import Chapter
import config

# 匹配中文章节标题行，如 "第一章 开端" / "第 12 章" / "第十章"
_CHAPTER_RE = re.compile(r"^\s*第\s*[0-9一二三四五六七八九十百零]+\s*章.*$")


def hard_split(text: str, chunk_chars: int = None) -> List[Chapter]:
    """章节识别失败时的兜底：按固定字数硬切。"""
    if chunk_chars is None:
        chunk_chars = config.HARD_SPLIT_CHARS
    text = text.strip()
    n = max(1, math.ceil(len(text) / chunk_chars))
    chapters: List[Chapter] = []
    for i in range(n):
        chunk = text[i * chunk_chars:(i + 1) * chunk_chars]
        chapters.append(Chapter(index=i + 1, title=f"第{i + 1}段", text=chunk))
    return chapters


def _split_by_headers(text: str) -> List[Chapter]:
    """按章节标题行切分；切不出（<2 章）则返回空列表交给硬切。"""
    lines = text.splitlines()
    header_idxs = [i for i, ln in enumerate(lines) if _CHAPTER_RE.match(ln)]
    if len(header_idxs) < 2:
        return []
    chapters: List[Chapter] = []
    for order, start in enumerate(header_idxs):
        end = header_idxs[order + 1] if order + 1 < len(header_idxs) else len(lines)
        title = lines[start].strip()
        body = "\n".join(lines[start + 1:end]).strip()
        chapters.append(Chapter(index=order + 1, title=title, text=body))
    return chapters


def parse_txt(path: str) -> List[Chapter]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    chapters = _split_by_headers(text)
    if not chapters:
        chapters = hard_split(text)
    return chapters


def parse_book(path: str) -> List[Chapter]:
    """按扩展名分派解析器：.txt / .epub / .pdf / .mobi。"""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".txt":
        return parse_txt(path)
    if ext == ".epub":
        from engine.parser_epub import parse_epub
        return parse_epub(path)
    if ext == ".pdf":
        from engine.parser_pdf import parse_pdf
        return parse_pdf(path)
    if ext == ".mobi":
        from engine.parser_mobi import parse_mobi
        return parse_mobi(path)
    raise ValueError(f"不支持的文件类型：{ext}")
