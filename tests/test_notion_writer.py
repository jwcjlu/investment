from unittest.mock import MagicMock, call
from engine.notion_writer import (
    write_opinion_rows,
    build_opinion_properties,
    sanitize_tags,
    write_overview_page,
    find_child_pages_by_title,
    overview_title,
)
from engine.models import OpinionEntry, BookSummary, ChapterNote


def _op():
    return OpinionEntry(
        opinion="永远不要满仓单一标的",
        chapter="第二章",
        tags=["风险控制", "仓位管理"],
        argument_summary="集中导致不可控回撤",
        actionability="原则",
        quote="不要把鸡蛋放在一个篮子里",
    )


def _summary():
    return BookSummary(
        book_title="聪明的投资者",
        author="格雷厄姆",
        one_liner="价值投资圣经",
        core_theses=["安全边际"],
        principles=["分散"],
        open_questions=["何时卖出"],
    )


def test_build_opinion_properties_maps_all_fields():
    props = build_opinion_properties(_op(), book_title="聪明的投资者")
    assert props["观点"]["title"][0]["text"]["content"] == "永远不要满仓单一标的"
    assert props["来源书"]["rich_text"][0]["text"]["content"] == "聪明的投资者"
    assert props["章节"]["rich_text"][0]["text"]["content"] == "第二章"
    tag_names = [t["name"] for t in props["主题标签"]["multi_select"]]
    assert "风险控制" in tag_names and "仓位管理" in tag_names
    assert props["可执行度"]["select"]["name"] == "原则"
    assert props["原文金句"]["rich_text"][0]["text"]["content"].startswith("不要把")


def test_sanitize_tags_drops_commas_and_junk():
    assert sanitize_tags([",", " ", "估值,风险控制", "bad]{", "财报分析"]) == [
        "估值", "风险控制", "财报分析",
    ]


def test_build_opinion_properties_strips_invalid_tags():
    op = _op()
    op.tags = [",", "风险控制", "opinion_placeholder],'"]
    props = build_opinion_properties(op, book_title="测试")
    tag_names = [t["name"] for t in props["主题标签"]["multi_select"]]
    assert tag_names == ["风险控制"]


def test_write_opinion_rows_archives_old_then_creates():
    client = MagicMock()
    client.databases.retrieve.return_value = {
        "data_sources": [{"id": "ds-1", "name": "投资观点"}],
    }
    client.data_sources.query.return_value = {
        "results": [{"id": "old1"}, {"id": "old2"}],
        "has_more": False,
    }
    write_opinion_rows(client, database_id="db123",
                       opinions=[_op()], book_title="聪明的投资者")
    client.data_sources.query.assert_called()
    assert client.pages.update.call_args_list == [
        call(page_id="old1", archived=True),
        call(page_id="old2", archived=True),
    ]
    assert client.pages.create.call_count == 1


def test_find_child_pages_by_title():
    client = MagicMock()
    client.blocks.children.list.return_value = {
        "results": [
            {"id": "a", "type": "child_page", "child_page": {"title": "📖 聪明的投资者（格雷厄姆）"}},
            {"id": "b", "type": "paragraph"},
            {"id": "c", "type": "child_page", "child_page": {"title": "其他"}},
            {"id": "d", "type": "child_page", "child_page": {"title": "📖 聪明的投资者（格雷厄姆）"}},
        ],
        "has_more": False,
    }
    ids = find_child_pages_by_title(
        client, "parent", "📖 聪明的投资者（格雷厄姆）")
    assert ids == ["a", "d"]


def test_write_overview_page_reuses_existing_and_archives_dupes():
    client = MagicMock()
    title = overview_title(_summary())
    client.blocks.children.list.side_effect = [
        # find existing
        {
            "results": [
                {"id": "keep", "type": "child_page", "child_page": {"title": title}},
                {"id": "dupe", "type": "child_page", "child_page": {"title": title}},
            ],
            "has_more": False,
        },
        # clear children of keep
        {
            "results": [{"id": "old-block"}],
            "has_more": False,
        },
    ]
    page_id = write_overview_page(
        client, "parent", _summary(),
        [ChapterNote(1, "第一章", ["点"], [], [], [], [], [])],
    )
    assert page_id == "keep"
    client.pages.update.assert_called_once_with(page_id="dupe", archived=True)
    client.blocks.delete.assert_called_once_with(block_id="old-block")
    client.blocks.children.append.assert_called()
    client.pages.create.assert_not_called()


def test_write_overview_page_creates_when_missing():
    client = MagicMock()
    client.blocks.children.list.return_value = {"results": [], "has_more": False}
    client.pages.create.return_value = {"id": "new-page"}
    page_id = write_overview_page(
        client, "parent", _summary(),
        [ChapterNote(1, "第一章", ["点"], [], [], [], [], [])],
    )
    assert page_id == "new-page"
    client.pages.create.assert_called_once()
