from __future__ import annotations
import os
import json
import re
from typing import List, Optional
from engine.models import ChapterNote, BookSummary

_DEFAULT_BASE = "output"


def _safe(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()


def _cache_dir(book: str, base: str) -> str:
    return os.path.join(base, ".cache", _safe(book))


def _note_path(book: str, index: int, base: str) -> str:
    return os.path.join(_cache_dir(book, base), f"第{index}章.json")


def has_chapter_note(book: str, index: int, base: str = _DEFAULT_BASE) -> bool:
    return os.path.exists(_note_path(book, index, base))


def save_chapter_note(book: str, note: ChapterNote, base: str = _DEFAULT_BASE) -> None:
    d = _cache_dir(book, base)
    os.makedirs(d, exist_ok=True)
    with open(_note_path(book, note.chapter_index, base), "w", encoding="utf-8") as f:
        json.dump(note.to_dict(), f, ensure_ascii=False, indent=2)


def _chapter_text_path(book: str, index: int, base: str) -> str:
    return os.path.join(_cache_dir(book, base), "_chapters", f"{index}.txt")


def save_chapter_text(
    book: str, index: int, text: str, base: str = _DEFAULT_BASE
) -> None:
    path = _chapter_text_path(book, index, base)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text or "")


def load_chapter_text(
    book: str, index: int, base: str = _DEFAULT_BASE
) -> Optional[str]:
    path = _chapter_text_path(book, index, base)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()


def load_chapter_note(book: str, index: int, base: str = _DEFAULT_BASE) -> Optional[ChapterNote]:
    p = _note_path(book, index, base)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return ChapterNote.from_dict(json.load(f))


def write_markdown(book: str, summary: BookSummary, notes: List[ChapterNote],
                   base: str = _DEFAULT_BASE) -> str:
    os.makedirs(base, exist_ok=True)
    path = os.path.join(base, f"{_safe(book)}.md")
    lines: List[str] = []
    lines.append(f"# 📖 {summary.book_title}（{summary.author}）\n")
    lines.append(f"**一句话总结：** {summary.one_liner}\n")
    lines.append("## 全书核心论点")
    lines += [f"- {t}" for t in summary.core_theses]
    lines.append("\n## 提炼的投资原则 / 可执行清单")
    lines += [f"- {p}" for p in summary.principles]
    lines.append("\n## 逐章笔记")
    for note in sorted(notes, key=lambda n: n.chapter_index):
        lines.append(f"\n### {note.chapter_title}")
        lines.append("**核心观点：**")
        lines += [f"- {x.text}" for x in note.core_points]
        lines.append("**论据：**")
        lines += [f"- {x.text}" for x in note.arguments]
        lines.append("**可执行要点：**")
        lines += [f"- {x.text}" for x in note.actionables]
        lines.append("**金句：**")
        lines += [f"> {x.text}" for x in note.quotes]
        if note.opinions:
            lines.append("**观点条目：**")
            for o in note.opinions:
                tags = "、".join(o.tags)
                lines.append(f"- {o.opinion} `[{tags}]` ({o.actionability})")
    lines.append("\n## 我的疑问 & 待验证点")
    lines += [f"- {q}" for q in summary.open_questions]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path
