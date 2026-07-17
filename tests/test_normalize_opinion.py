from engine.reader import normalize_opinion, normalize_chapter_payload


def test_normalize_opinion_english_keys():
    entry = normalize_opinion(
        {
            "opinion": "安全边际",
            "tags": ["估值"],
            "argument_summary": "低买",
            "actionability": "原则",
            "quote": "margin of safety",
        },
        chapter="第一章",
    )
    assert entry.opinion == "安全边际"
    assert entry.chapter == "第一章"
    assert entry.tags == ["估值"]


def test_normalize_opinion_chinese_aliases():
    entry = normalize_opinion(
        {
            "观点": "别满仓",
            "标签": ["仓位管理"],
            "论据摘要": "分散",
            "可执行度": "可直接执行",
            "金句": "不要把鸡蛋放一个篮子",
        },
        chapter="第二章",
    )
    assert entry.opinion == "别满仓"
    assert entry.tags == ["仓位管理"]
    assert entry.argument_summary == "分散"
    assert entry.actionability == "可直接执行"
    assert entry.quote == "不要把鸡蛋放一个篮子"


def test_normalize_opinion_string_item():
    entry = normalize_opinion("现金流比利润更重要", chapter="第3章")
    assert entry.opinion == "现金流比利润更重要"
    assert entry.actionability == "原则"


def test_normalize_opinion_coerces_nested_opinion_object():
    entry = normalize_opinion(
        {
            "opinion": {"text": "指数基金适合定投"},
            "tags": ["分散化"],
            "argument_summary": "波动可摊平",
            "actionability": "可直接执行",
            "quote": "定投",
        },
        chapter="第4章",
    )
    assert entry is not None
    assert entry.opinion == "指数基金适合定投"


def test_normalize_chapter_payload_skips_empty_opinions():
    data = normalize_chapter_payload(
        {
            "core_points": ["a"],
            "arguments": [],
            "actionables": [],
            "quotes": [],
            "opinions": [
                {"tags": ["估值"]},  # 无观点正文 → 跳过
                {"opinion": "ok", "tags": ["估值"], "argument_summary": "", "actionability": "原则", "quote": ""},
            ],
            "suggested_tags": [],
        }
    )
    assert len(data["opinions"]) == 1
    assert data["opinions"][0]["opinion"] == "ok"
