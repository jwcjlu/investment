from __future__ import annotations
from typing import List, Optional
from engine.models import OpinionEntry, BookSummary, ChapterNote


def _rt(text: str) -> dict:
    return {"rich_text": [{"text": {"content": text[:2000]}}]}


def _title(text: str) -> dict:
    return {"title": [{"text": {"content": text[:2000]}}]}


def sanitize_tags(tags: List[str]) -> List[str]:
    """清洗主题标签：Notion multi_select 不允许逗号，并去掉空/垃圾项。"""
    out: List[str] = []
    seen = set()
    for raw in tags or []:
        text = str(raw).replace("，", ",")
        for part in text.split(","):
            name = part.strip()
            if not name or name in seen:
                continue
            # 模型偶发把 JSON 碎片写进 tags
            if any(ch in name for ch in "{}[]'\""):
                continue
            if all(ch in ".,;:|/\\-_" for ch in name):
                continue
            name = name[:100]
            seen.add(name)
            out.append(name)
    return out


def overview_title(summary: BookSummary) -> str:
    return f"📖 {summary.book_title}（{summary.author}）"


def build_opinion_properties(op: OpinionEntry, book_title: str) -> dict:
    tags = sanitize_tags(op.tags)
    return {
        "观点": _title(op.opinion),
        "来源书": _rt(book_title),
        "章节": _rt(op.chapter),
        "主题标签": {"multi_select": [{"name": t} for t in tags]},
        "论据摘要": _rt(op.argument_summary),
        "可执行度": {"select": {"name": op.actionability}},
        "原文金句": _rt(op.quote),
    }


def _iter_block_children(client, block_id: str):
    cursor: Optional[str] = None
    while True:
        kwargs = {"block_id": block_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = client.blocks.children.list(**kwargs)
        for item in resp.get("results", []):
            yield item
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")


def find_child_pages_by_title(client, parent_page_id: str, title: str) -> List[str]:
    """在父页面下查找标题完全匹配的子页面 ID（可能有重复）。"""
    ids: List[str] = []
    for block in _iter_block_children(client, parent_page_id):
        if block.get("type") != "child_page":
            continue
        if block.get("child_page", {}).get("title") == title:
            ids.append(block["id"])
    return ids


def clear_block_children(client, block_id: str) -> None:
    """删除页面下所有子块，便于覆写内容。"""
    for block in list(_iter_block_children(client, block_id)):
        client.blocks.delete(block_id=block["id"])


def append_blocks(client, page_id: str, blocks: List[dict]) -> None:
    for i in range(0, len(blocks), 100):
        client.blocks.children.append(block_id=page_id, children=blocks[i:i + 100])


def archive_pages(client, page_ids: List[str]) -> None:
    for pid in page_ids:
        client.pages.update(page_id=pid, archived=True)


def resolve_data_source_id(client, database_id: str) -> str:
    """Notion 2025-09 起：database 是容器，查询要用其下 data_source_id。"""
    db = client.databases.retrieve(database_id=database_id)
    sources = db.get("data_sources") or []
    if not sources:
        raise RuntimeError(f"数据库 {database_id} 没有 data_sources，无法查询。")
    return sources[0]["id"]


def find_opinion_pages_for_book(client, database_id: str, book_title: str) -> List[str]:
    """查出观点库中来源书=book_title 的所有页面。"""
    data_source_id = resolve_data_source_id(client, database_id)
    ids: List[str] = []
    cursor: Optional[str] = None
    while True:
        kwargs = {
            "data_source_id": data_source_id,
            "page_size": 100,
            "filter": {
                "property": "来源书",
                "rich_text": {"equals": book_title},
            },
        }
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = client.data_sources.query(**kwargs)
        for page in resp.get("results", []):
            ids.append(page["id"])
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return ids


def write_opinion_rows(client, database_id: str,
                       opinions: List[OpinionEntry], book_title: str) -> int:
    """按书覆盖写入观点：先归档该书旧行，再创建新行，避免重复。"""
    old_ids = find_opinion_pages_for_book(client, database_id, book_title)
    if old_ids:
        archive_pages(client, old_ids)
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
    """按书名幂等写入总览：已存在则覆写并归档多余副本，不存在则新建。"""
    title = overview_title(summary)
    blocks = build_overview_blocks(summary, notes)
    existing = find_child_pages_by_title(client, parent_page_id, title)

    if existing:
        page_id = existing[0]
        if len(existing) > 1:
            archive_pages(client, existing[1:])
        clear_block_children(client, page_id)
        append_blocks(client, page_id, blocks)
        return page_id

    page = client.pages.create(
        parent={"page_id": parent_page_id},
        properties={"title": [{"text": {"content": title}}]},
        children=blocks[:100],
    )
    page_id = page["id"]
    if len(blocks) > 100:
        append_blocks(client, page_id, blocks[100:])
    return page_id
