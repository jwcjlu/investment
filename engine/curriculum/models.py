from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from engine.models import OpinionEntry, ChapterNote


@dataclass
class CatalogItem:
    """带书名的观点 + 可选章节笔记引用。"""
    book_title: str
    opinion: OpinionEntry
    chapter_index: Optional[int] = None  # 用于查章节笔记；Notion-only 可为 None

    def to_dict(self) -> dict:
        return {
            "book_title": self.book_title,
            "opinion": self.opinion.to_dict(),
            "chapter_index": self.chapter_index,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CatalogItem":
        return cls(
            book_title=d["book_title"],
            opinion=OpinionEntry.from_dict(d["opinion"]),
            chapter_index=d.get("chapter_index"),
        )


@dataclass
class Lesson:
    lesson_id: str
    book_title: str
    chapter: str
    chapter_index: Optional[int]
    opinion: str
    argument_summary: str
    actionability: str
    quote: str
    tags: List[str]


@dataclass
class Module:
    tag: str
    lessons: List[Lesson]


@dataclass
class ModuleIntro:
    tag: str
    goals: str
    cross_book: str
    study_order_note: str
    source: str  # "ai" | "placeholder"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ModuleIntro":
        return cls(**d)


@dataclass
class ProgressState:
    completed: List[str] = field(default_factory=list)
    last_lesson_id: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ProgressState":
        return cls(
            completed=list(d.get("completed") or []),
            last_lesson_id=d.get("last_lesson_id"),
            updated_at=d.get("updated_at"),
        )
