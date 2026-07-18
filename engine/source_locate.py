"""在章节正文中定位摘录并切出侧栏窗口。"""

from __future__ import annotations

import unicodedata
from typing import Optional, Tuple


def _collapse_ws_with_map(text: str) -> tuple[str, list[int]]:
    """返回规范化文本，以及每个规范字符对应的原文起始下标。"""
    norm_chars: list[str] = []
    map_to_orig: list[int] = []
    prev_space = False
    for i, ch in enumerate(unicodedata.normalize("NFKC", text)):
        if ch.isspace():
            if not prev_space and norm_chars:
                norm_chars.append(" ")
                map_to_orig.append(i)
                prev_space = True
            continue
        prev_space = False
        norm_chars.append(ch)
        map_to_orig.append(i)
    return "".join(norm_chars), map_to_orig


def locate_excerpt(
    chapter_text: str, excerpt: str
) -> Tuple[Optional[int], Optional[int]]:
    """Return char_start/end in original chapter_text, or (None, None)."""
    if not chapter_text or not excerpt:
        return None, None
    idx = chapter_text.find(excerpt)
    if idx >= 0:
        return idx, idx + len(excerpt)

    norm_text, map_to_orig = _collapse_ws_with_map(chapter_text)
    norm_ex, _ = _collapse_ws_with_map(excerpt)
    norm_ex = norm_ex.strip()
    if not norm_ex:
        return None, None
    j = norm_text.find(norm_ex)
    if j < 0:
        return None, None
    start = map_to_orig[j]
    end_j = j + len(norm_ex) - 1
    end = map_to_orig[end_j] + 1
    return start, end


def slice_window(
    chapter_text: str,
    char_start: Optional[int],
    char_end: Optional[int],
    *,
    excerpt: Optional[str] = None,
    pad: int = 800,
    hard_max: int = 4000,
) -> tuple[str, Optional[tuple[int, int]]]:
    """Return (window_text, highlight_relative_or_None)."""
    if not chapter_text:
        text = (excerpt or "")[:hard_max]
        return text, None

    if char_start is None or char_end is None:
        if excerpt:
            char_start, char_end = locate_excerpt(chapter_text, excerpt)
        if char_start is None or char_end is None:
            text = (excerpt or "")[:hard_max]
            return text, None

    lo = max(0, char_start - pad)
    hi = min(len(chapter_text), char_end + pad)
    if hi - lo > hard_max:
        mid = (char_start + char_end) // 2
        lo = max(0, mid - hard_max // 2)
        hi = min(len(chapter_text), lo + hard_max)
        lo = max(0, hi - hard_max)

    window = chapter_text[lo:hi]
    return window, (char_start - lo, char_end - lo)
