from engine.models import OpinionEntry
from engine.curriculum.models import CatalogItem
from engine.curriculum.assembler import assemble_modules
from engine.curriculum.lesson_id import make_lesson_id


def _item(book, chapter, opinion, tags, actionability, idx=1):
    return CatalogItem(
        book_title=book,
        chapter_index=idx,
        opinion=OpinionEntry(
            opinion=opinion,
            chapter=chapter,
            tags=tags,
            argument_summary="论据",
            actionability=actionability,
            quote="金句",
        ),
    )


def test_assemble_groups_by_tag_and_skips_empty():
    items = [
        _item("A书", "第1章", "观点1", ["估值"], "原则"),
        _item("B书", "第2章", "观点2", ["风险控制"], "可直接执行"),
    ]
    modules = assemble_modules(items)
    tags = [m.tag for m in modules]
    assert "估值" in tags
    assert "风险控制" in tags
    assert "复利" not in tags  # 无观点不展示


def test_assemble_difficulty_order():
    items = [
        _item("A", "章", "需判断的", ["估值"], "需自己判断"),
        _item("A", "章", "可执行的", ["估值"], "可直接执行"),
        _item("A", "章", "原则性的", ["估值"], "原则"),
    ]
    mod = next(m for m in assemble_modules(items) if m.tag == "估值")
    assert [l.actionability for l in mod.lessons] == [
        "原则", "可直接执行", "需自己判断"
    ]


def test_multi_tag_appears_in_multiple_modules_same_id():
    items = [_item("A", "章", "跨标签", ["估值", "分散化"], "原则")]
    modules = assemble_modules(items)
    by_tag = {m.tag: m for m in modules}
    id1 = by_tag["估值"].lessons[0].lesson_id
    id2 = by_tag["分散化"].lessons[0].lesson_id
    assert id1 == id2 == make_lesson_id("A", "章", "跨标签")
