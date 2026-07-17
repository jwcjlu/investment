from __future__ import annotations
from typing import List, Dict
import config
from engine.curriculum.models import CatalogItem, Lesson, Module
from engine.curriculum.lesson_id import make_lesson_id

_ACTION_ORDER = {name: i for i, name in enumerate(config.ACTIONABILITY_VALUES)}


def _to_lesson(item: CatalogItem) -> Lesson:
    op = item.opinion
    return Lesson(
        lesson_id=make_lesson_id(item.book_title, op.chapter, op.opinion),
        book_title=item.book_title,
        chapter=op.chapter,
        chapter_index=item.chapter_index,
        opinion=op.opinion,
        argument_summary=op.argument_summary,
        actionability=op.actionability,
        quote=op.quote,
        tags=list(op.tags),
    )


def assemble_modules(items: List[CatalogItem]) -> List[Module]:
    buckets: Dict[str, List[Lesson]] = {t: [] for t in config.FIXED_TAGS}
    for item in items:
        lesson = _to_lesson(item)
        for tag in item.opinion.tags:
            if tag in buckets:
                buckets[tag].append(lesson)
    modules: List[Module] = []
    for tag in config.FIXED_TAGS:
        lessons = buckets[tag]
        if not lessons:
            continue
        lessons.sort(
            key=lambda L: (
                _ACTION_ORDER.get(L.actionability, 99),
                L.book_title,
                L.chapter,
                L.opinion,
            )
        )
        modules.append(Module(tag=tag, lessons=lessons))
    return modules
