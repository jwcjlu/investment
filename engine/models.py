from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, List, Optional


@dataclass
class Chapter:
    index: int
    title: str
    text: str


@dataclass
class SourceRef:
    book_title: str
    chapter_index: int
    excerpt: str
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    para_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "book_title": self.book_title,
            "chapter_index": self.chapter_index,
            "excerpt": self.excerpt,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "para_id": self.para_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SourceRef":
        return cls(
            book_title=d["book_title"],
            chapter_index=int(d["chapter_index"]),
            excerpt=d.get("excerpt") or "",
            char_start=d.get("char_start"),
            char_end=d.get("char_end"),
            para_id=d.get("para_id"),
        )


@dataclass
class NoteAtom:
    text: str
    sources: List[SourceRef] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "sources": [s.to_dict() for s in self.sources],
        }

    @classmethod
    def from_any(cls, raw: Any) -> "NoteAtom":
        if isinstance(raw, str):
            return cls(text=raw.strip(), sources=[])
        if isinstance(raw, dict):
            text = str(raw.get("text") or "").strip()
            sources = [
                SourceRef.from_dict(s) for s in (raw.get("sources") or []) if isinstance(s, dict)
            ]
            return cls(text=text, sources=sources)
        return cls(text=str(raw).strip(), sources=[])


@dataclass
class OpinionEntry:
    opinion: str                 # 观点（标题）
    chapter: str                 # 出处章节
    tags: List[str]              # 主题标签（取自固定表）
    argument_summary: str        # 论据摘要
    actionability: str           # 原则 / 可直接执行 / 需自己判断
    quote: str                   # 原文金句
    sources: List[SourceRef] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "OpinionEntry":
        sources = [
            SourceRef.from_dict(s) for s in (d.get("sources") or []) if isinstance(s, dict)
        ]
        return cls(
            opinion=d["opinion"],
            chapter=d["chapter"],
            tags=list(d.get("tags") or []),
            argument_summary=d.get("argument_summary") or "",
            actionability=d.get("actionability") or "原则",
            quote=d.get("quote") or "",
            sources=sources,
        )


@dataclass
class ChapterNote:
    chapter_index: int
    chapter_title: str
    core_points: List[NoteAtom]
    arguments: List[NoteAtom]
    actionables: List[NoteAtom]
    quotes: List[NoteAtom]
    opinions: List[OpinionEntry] = field(default_factory=list)
    suggested_tags: List[str] = field(default_factory=list)  # 建议新增标签

    def __post_init__(self) -> None:
        self.core_points = [
            x if isinstance(x, NoteAtom) else NoteAtom.from_any(x) for x in self.core_points
        ]
        self.arguments = [
            x if isinstance(x, NoteAtom) else NoteAtom.from_any(x) for x in self.arguments
        ]
        self.actionables = [
            x if isinstance(x, NoteAtom) else NoteAtom.from_any(x) for x in self.actionables
        ]
        self.quotes = [
            x if isinstance(x, NoteAtom) else NoteAtom.from_any(x) for x in self.quotes
        ]

    def to_dict(self) -> dict:
        return {
            "chapter_index": self.chapter_index,
            "chapter_title": self.chapter_title,
            "core_points": [a.to_dict() for a in self.core_points],
            "arguments": [a.to_dict() for a in self.arguments],
            "actionables": [a.to_dict() for a in self.actionables],
            "quotes": [a.to_dict() for a in self.quotes],
            "opinions": [o.to_dict() for o in self.opinions],
            "suggested_tags": list(self.suggested_tags),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ChapterNote":
        opinions = [OpinionEntry.from_dict(o) for o in d.get("opinions", [])]
        return cls(
            chapter_index=d["chapter_index"],
            chapter_title=d["chapter_title"],
            core_points=[NoteAtom.from_any(x) for x in d.get("core_points") or []],
            arguments=[NoteAtom.from_any(x) for x in d.get("arguments") or []],
            actionables=[NoteAtom.from_any(x) for x in d.get("actionables") or []],
            quotes=[NoteAtom.from_any(x) for x in d.get("quotes") or []],
            opinions=opinions,
            suggested_tags=d.get("suggested_tags", []),
        )


@dataclass
class BookSummary:
    book_title: str
    author: str
    one_liner: str
    core_theses: List[str]
    principles: List[str]
    open_questions: List[str]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "BookSummary":
        return cls(**d)
