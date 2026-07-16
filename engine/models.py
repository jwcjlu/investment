from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List


@dataclass
class Chapter:
    index: int
    title: str
    text: str


@dataclass
class OpinionEntry:
    opinion: str                 # 观点（标题）
    chapter: str                 # 出处章节
    tags: List[str]              # 主题标签（取自固定表）
    argument_summary: str        # 论据摘要
    actionability: str           # 原则 / 可直接执行 / 需自己判断
    quote: str                   # 原文金句

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "OpinionEntry":
        return cls(**d)


@dataclass
class ChapterNote:
    chapter_index: int
    chapter_title: str
    core_points: List[str]
    arguments: List[str]
    actionables: List[str]
    quotes: List[str]
    opinions: List[OpinionEntry] = field(default_factory=list)
    suggested_tags: List[str] = field(default_factory=list)  # 建议新增标签

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ChapterNote":
        opinions = [OpinionEntry.from_dict(o) for o in d.get("opinions", [])]
        return cls(
            chapter_index=d["chapter_index"],
            chapter_title=d["chapter_title"],
            core_points=d["core_points"],
            arguments=d["arguments"],
            actionables=d["actionables"],
            quotes=d["quotes"],
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
