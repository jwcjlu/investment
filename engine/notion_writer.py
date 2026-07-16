from __future__ import annotations
from typing import List
from engine.models import OpinionEntry, BookSummary, ChapterNote


def _rt(text: str) -> dict:
    return {"rich_text": [{"text": {"content": text[:2000]}}]}


def _title(text: str) -> dict:
    return {"title": [{"text": {"content": text[:2000]}}]}


def build_opinion_properties(op: OpinionEntry, book_title: str) -> dict:
    return {
        "观点": _title(op.opinion),
        "来源书": _rt(book_title),
        "章节": _rt(op.chapter),
        "主题标签": {"multi_select": [{"name": t} for t in op.tags]},
        "论据摘要": _rt(op.argument_summary),
        "可执行度": {"select": {"name": op.actionability}},
        "原文金句": _rt(op.quote),
    }


def write_opinion_rows(client, database_id: str,
                       opinions: List[OpinionEntry], book_title: str) -> int:
    count = 0
    for op in opinions:
        client.pages.create(
            parent={"database_id": database_id},
            properties=build_opinion_properties(op, book_title),
        )
        count += 1
    return count


def _para(text: str) -> dict:
    return {"object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{"text": {"content": text[:2000]}}]}}


def _heading(text: str) -> dict:
    return {"object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [{"text": {"content": text[:2000]}}]}}


def _bullet(text: str) -> dict:
    return {"object": "block", "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [{"text": {"content": text[:2000]}}]}}


def build_overview_blocks(summary: BookSummary, notes: List[ChapterNote]) -> List[dict]:
    blocks: List[dict] = []
    blocks.append(_para(f"一句话总结：{summary.one_liner}"))
    blocks.append(_heading("全书核心论点"))
    blocks += [_bullet(t) for t in summary.core_theses]
    blocks.append(_heading("提炼的投资原则 / 可执行清单"))
    blocks += [_bullet(p) for p in summary.principles]
    blocks.append(_heading("逐章笔记"))
    for n in sorted(notes, key=lambda x: x.chapter_index):
        blocks.append(_heading(n.chapter_title))
        for x in n.core_points:
            blocks.append(_bullet(f"核心：{x}"))
        for x in n.actionables:
            blocks.append(_bullet(f"可执行：{x}"))
        for x in n.quotes:
            blocks.append(_bullet(f"金句：{x}"))
    blocks.append(_heading("我的疑问 & 待验证点"))
    blocks += [_bullet(q) for q in summary.open_questions]
    return blocks


def write_overview_page(client, parent_page_id: str,
                        summary: BookSummary, notes: List[ChapterNote]) -> str:
    # Notion 单次 children 上限 100，分批追加
    blocks = build_overview_blocks(summary, notes)
    page = client.pages.create(
        parent={"page_id": parent_page_id},
        properties={"title": [{"text": {"content":
                    f"📖 {summary.book_title}（{summary.author}）"}}]},
        children=blocks[:100],
    )
    page_id = page["id"]
    for i in range(100, len(blocks), 100):
        client.blocks.children.append(block_id=page_id, children=blocks[i:i + 100])
    return page_id
