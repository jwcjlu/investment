from unittest.mock import MagicMock, patch

from engine.models import OpinionEntry
from engine.curriculum.models import CatalogItem
from engine.curriculum.notion_sync import (
    merge_catalog,
    rows_to_catalog_items,
    fetch_notion_opinion_rows,
    sync_and_merge,
)


def _item(book, chapter, opinion, idx=1, **op_kwargs):
    defaults = dict(
        tags=["估值"],
        argument_summary="论据",
        actionability="原则",
        quote="金句",
    )
    defaults.update(op_kwargs)
    return CatalogItem(
        book_title=book,
        chapter_index=idx,
        opinion=OpinionEntry(opinion=opinion, chapter=chapter, **defaults),
    )


def _notion_page(
    opinion="观点A",
    book="聪明书",
    chapter="第1章",
    tags=None,
    actionability="原则",
    argument="论据摘要",
    quote="原文金句",
):
    tags = tags or ["估值"]
    props = {
        "观点": {"title": [{"plain_text": opinion}]},
        "来源书": {"rich_text": [{"plain_text": book}]},
        "章节": {"rich_text": [{"plain_text": chapter}]},
        "主题标签": {"multi_select": [{"name": t} for t in tags]},
        "论据摘要": {"rich_text": [{"plain_text": argument}]},
        "原文金句": {"rich_text": [{"plain_text": quote}]},
    }
    if actionability is not None:
        props["可执行度"] = {"select": {"name": actionability}}
    return {"id": "page-1", "properties": props}


def test_merge_catalog_local_wins_on_duplicate_key():
    local = [_item("A书", "第1章", "相同观点", idx=3)]
    remote = [_item("A书", "第1章", "相同观点", idx=None)]
    merged = merge_catalog(local, remote)
    assert len(merged) == 1
    assert merged[0].chapter_index == 3


def test_merge_catalog_appends_notion_only_items():
    local = [_item("A书", "第1章", "本地独有")]
    remote = [
        _item("A书", "第1章", "本地独有", idx=None),
        _item("B书", "第2章", "Notion独有", idx=None),
    ]
    merged = merge_catalog(local, remote)
    assert len(merged) == 2
    titles = {(i.book_title, i.opinion.opinion) for i in merged}
    assert ("A书", "本地独有") in titles
    assert ("B书", "Notion独有") in titles
    notion_only = next(i for i in merged if i.book_title == "B书")
    assert notion_only.chapter_index is None


def test_rows_to_catalog_items_maps_notion_properties():
    pages = [_notion_page()]
    items = rows_to_catalog_items(pages)
    assert len(items) == 1
    item = items[0]
    assert item.book_title == "聪明书"
    assert item.chapter_index is None
    assert item.opinion.opinion == "观点A"
    assert item.opinion.chapter == "第1章"
    assert item.opinion.tags == ["估值"]
    assert item.opinion.argument_summary == "论据摘要"
    assert item.opinion.actionability == "原则"
    assert item.opinion.quote == "原文金句"


def test_rows_to_catalog_items_joins_rich_text_chunks():
    page = _notion_page(book="书", chapter="章")
    page["properties"]["来源书"]["rich_text"] = [
        {"plain_text": "书"},
        {"plain_text": "名"},
    ]
    page["properties"]["章节"]["rich_text"] = [
        {"plain_text": "第"},
        {"plain_text": "1章"},
    ]
    item = rows_to_catalog_items([page])[0]
    assert item.book_title == "书名"
    assert item.opinion.chapter == "第1章"


def test_rows_to_catalog_items_defaults_actionability_when_missing():
    page = _notion_page(actionability=None)
    item = rows_to_catalog_items([page])[0]
    assert item.opinion.actionability == "原则"


@patch("engine.curriculum.notion_sync.resolve_data_source_id")
def test_fetch_notion_opinion_rows_paginates(mock_resolve):
    mock_resolve.return_value = "ds-1"
    client = MagicMock()
    client.data_sources.query.side_effect = [
        {
            "results": [{"id": "p1", "properties": {}}],
            "has_more": True,
            "next_cursor": "cursor-1",
        },
        {
            "results": [{"id": "p2", "properties": {}}],
            "has_more": False,
        },
    ]
    rows = fetch_notion_opinion_rows(client, "db123")
    assert [r["id"] for r in rows] == ["p1", "p2"]
    assert client.data_sources.query.call_count == 2
    first_call = client.data_sources.query.call_args_list[0]
    assert first_call.kwargs["data_source_id"] == "ds-1"
    assert first_call.kwargs["page_size"] == 100
    assert "start_cursor" not in first_call.kwargs
    second_call = client.data_sources.query.call_args_list[1]
    assert second_call.kwargs["start_cursor"] == "cursor-1"
    mock_resolve.assert_called_once_with(client, "db123")


@patch("engine.curriculum.notion_sync.fetch_notion_opinion_rows")
def test_sync_and_merge(mock_fetch):
    local = [_item("A书", "第1章", "本地")]
    remote_page = _notion_page(
        opinion="Notion独有", book="B书", chapter="第2章"
    )
    mock_fetch.return_value = [remote_page]
    merged = sync_and_merge(local, MagicMock(), "db123")
    assert len(merged) == 2
    assert any(i.book_title == "A书" and i.chapter_index == 1 for i in merged)
    notion_only = next(i for i in merged if i.book_title == "B书")
    assert notion_only.chapter_index is None
