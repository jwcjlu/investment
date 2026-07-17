from __future__ import annotations

from typing import List, Optional, Tuple

from engine.models import OpinionEntry
from engine.curriculum.models import CatalogItem
from engine.notion_writer import resolve_data_source_id


def _merge_key(item: CatalogItem) -> Tuple[str, str, str]:
    return (item.book_title, item.opinion.chapter, item.opinion.opinion)


def merge_catalog(
    local_items: List[CatalogItem],
    remote_items: List[CatalogItem],
) -> List[CatalogItem]:
    """合并本地与 Notion 目录：相同键保留本地（含 chapter_index），Notion 独有追加。"""
    local_keys = {_merge_key(item) for item in local_items}
    merged = list(local_items)
    for item in remote_items:
        if _merge_key(item) not in local_keys:
            merged.append(item)
    return merged


def _plain_text(chunks: list) -> str:
    parts: List[str] = []
    for chunk in chunks or []:
        if chunk.get("plain_text") is not None:
            parts.append(chunk["plain_text"])
        elif chunk.get("text", {}).get("content") is not None:
            parts.append(chunk["text"]["content"])
    return "".join(parts)


def _page_to_catalog_item(page: dict) -> Optional[CatalogItem]:
    props = page.get("properties") or {}

    opinion = _plain_text((props.get("观点") or {}).get("title"))
    book_title = _plain_text((props.get("来源书") or {}).get("rich_text"))
    chapter = _plain_text((props.get("章节") or {}).get("rich_text"))
    argument_summary = _plain_text((props.get("论据摘要") or {}).get("rich_text"))
    quote = _plain_text((props.get("原文金句") or {}).get("rich_text"))

    tag_prop = props.get("主题标签") or {}
    tags = [t["name"] for t in tag_prop.get("multi_select") or [] if t.get("name")]

    actionability_prop = props.get("可执行度") or {}
    select = actionability_prop.get("select")
    actionability = select.get("name") if select else "原则"

    return CatalogItem(
        book_title=book_title,
        chapter_index=None,
        opinion=OpinionEntry(
            opinion=opinion,
            chapter=chapter,
            tags=tags,
            argument_summary=argument_summary,
            actionability=actionability,
            quote=quote,
        ),
    )


def rows_to_catalog_items(notion_pages: List[dict]) -> List[CatalogItem]:
    """将 Notion 观点行转为 CatalogItem（build_opinion_properties 的逆操作）。"""
    items: List[CatalogItem] = []
    for page in notion_pages:
        item = _page_to_catalog_item(page)
        if item is not None:
            items.append(item)
    return items


def fetch_notion_opinion_rows(client, database_id: str) -> List[dict]:
    """分页拉取观点库全部行（无 filter）。"""
    data_source_id = resolve_data_source_id(client, database_id)
    rows: List[dict] = []
    cursor: Optional[str] = None
    while True:
        kwargs = {
            "data_source_id": data_source_id,
            "page_size": 100,
        }
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = client.data_sources.query(**kwargs)
        rows.extend(resp.get("results") or [])
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return rows


def sync_and_merge(
    local_items: List[CatalogItem],
    client,
    db_id: str,
) -> List[CatalogItem]:
    """拉取 Notion 观点并与本地目录合并。"""
    remote_pages = fetch_notion_opinion_rows(client, db_id)
    remote_items = rows_to_catalog_items(remote_pages)
    return merge_catalog(local_items, remote_items)
