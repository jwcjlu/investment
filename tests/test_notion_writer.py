from unittest.mock import MagicMock
from engine.notion_writer import write_opinion_rows, build_opinion_properties
from engine.models import OpinionEntry


def _op():
    return OpinionEntry(
        opinion="永远不要满仓单一标的",
        chapter="第二章",
        tags=["风险控制", "仓位管理"],
        argument_summary="集中导致不可控回撤",
        actionability="原则",
        quote="不要把鸡蛋放在一个篮子里",
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


def test_write_opinion_rows_calls_create_per_opinion():
    client = MagicMock()
    write_opinion_rows(client, database_id="db123",
                       opinions=[_op(), _op()], book_title="聪明的投资者")
    assert client.pages.create.call_count == 2
    _, kwargs = client.pages.create.call_args
    assert kwargs["parent"] == {"database_id": "db123"}
