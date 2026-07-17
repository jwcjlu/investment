from __future__ import annotations
from typing import Any, Dict, List, Optional
from engine.models import Chapter, ChapterNote, OpinionEntry
from engine.llm import make_client, create_structured
from engine.notion_writer import sanitize_tags
import config

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = make_client()
    return _client

# 每章笔记的 JSON schema（结构化输出，保证干净 JSON）
_CHAPTER_SCHEMA = {
    "type": "object",
    "properties": {
        "core_points": {"type": "array", "items": {"type": "string"}},
        "arguments": {"type": "array", "items": {"type": "string"}},
        "actionables": {"type": "array", "items": {"type": "string"}},
        "quotes": {"type": "array", "items": {"type": "string"}},
        "opinions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "opinion": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "argument_summary": {"type": "string"},
                    "actionability": {"type": "string", "enum": config.ACTIONABILITY_VALUES},
                    "quote": {"type": "string"},
                },
                "required": ["opinion", "tags", "argument_summary", "actionability", "quote"],
                "additionalProperties": False,
            },
        },
        "suggested_tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["core_points", "arguments", "actionables", "quotes", "opinions", "suggested_tags"],
    "additionalProperties": False,
}

_OPINION_FIELD_ALIASES = {
    "opinion": ("opinion", "观点", "核心观点", "text", "content", "title", "point", "core_point"),
    "tags": ("tags", "标签", "theme_tags", "topics"),
    "argument_summary": ("argument_summary", "论据摘要", "argument", "summary", "reason"),
    "actionability": ("actionability", "可执行度", "action"),
    "quote": ("quote", "金句", "原文金句", "citation"),
}


def _pick(raw: dict, keys: tuple) -> Any:
    for k in keys:
        if k in raw and raw[k] is not None:
            return raw[k]
    return None


def _as_text(value: Any) -> str:
    """把模型偶发的非字符串字段尽量收成文本。"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts = [_as_text(v) for v in value]
        return "；".join(p for p in parts if p)
    if isinstance(value, dict):
        for k in ("text", "content", "opinion", "观点", "value"):
            if k in value:
                t = _as_text(value[k])
                if t:
                    return t
        # 退而求其次：拼所有字符串值
        parts = [_as_text(v) for v in value.values()]
        return "；".join(p for p in parts if p)
    return str(value).strip()


def normalize_opinion(raw: Any, chapter: str) -> Optional[OpinionEntry]:
    """把模型返回的观点条目归一成 OpinionEntry；无法提取观点正文时返回 None。"""
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        return OpinionEntry(
            opinion=text,
            chapter=chapter,
            tags=[],
            argument_summary="",
            actionability="原则",
            quote="",
        )
    if not isinstance(raw, dict):
        return None

    opinion = _as_text(_pick(raw, _OPINION_FIELD_ALIASES["opinion"]))
    if not opinion:
        return None

    tags_raw = _pick(raw, _OPINION_FIELD_ALIASES["tags"])
    if isinstance(tags_raw, str):
        tags = [tags_raw] if tags_raw.strip() else []
    elif isinstance(tags_raw, list):
        tags = [str(t) for t in tags_raw if t]
    else:
        tags = []
    tags = sanitize_tags(tags)

    argument_summary = _as_text(_pick(raw, _OPINION_FIELD_ALIASES["argument_summary"]))

    actionability = _pick(raw, _OPINION_FIELD_ALIASES["actionability"])
    if isinstance(actionability, str):
        actionability = actionability.strip()
    if actionability not in config.ACTIONABILITY_VALUES:
        actionability = "原则"

    quote = _as_text(_pick(raw, _OPINION_FIELD_ALIASES["quote"]))

    return OpinionEntry(
        opinion=opinion,
        chapter=chapter,
        tags=tags,
        argument_summary=argument_summary,
        actionability=actionability,
        quote=quote,
    )


def normalize_chapter_payload(data: dict) -> dict:
    """校验并清洗章节 JSON；opinions 统一为标准英文字段。"""
    for key in ("core_points", "arguments", "actionables", "quotes", "opinions", "suggested_tags"):
        if key not in data:
            data[key] = []
        if not isinstance(data[key], list):
            raise ValueError(f"字段 {key} 应为数组，实际为 {type(data[key]).__name__}: {data[key]!r:.200}")

    cleaned: List[dict] = []
    for i, item in enumerate(data["opinions"]):
        entry = normalize_opinion(item, chapter="")
        if entry is None:
            keys = list(item.keys()) if isinstance(item, dict) else type(item).__name__
            sample = repr(item)[:160] if not isinstance(item, dict) else repr(item.get("opinion"))[:120]
            print(f"      警告：跳过无效 opinion[{i}] keys={keys} opinion={sample}")
            continue
        cleaned.append({
            "opinion": entry.opinion,
            "tags": entry.tags,
            "argument_summary": entry.argument_summary,
            "actionability": entry.actionability,
            "quote": entry.quote,
        })
    data["opinions"] = cleaned
    return data


def _build_prompt(chapter: Chapter) -> str:
    tag_list = "、".join(config.FIXED_TAGS)
    actionability = "、".join(config.ACTIONABILITY_VALUES)
    return f"""你是一位严谨的投资书籍精读助手。请精读下面这一章，提炼结构化笔记。

要求：
- 忠于原文，不臆造。金句必须是原文引用。
- opinions（核心观点）中每条必须是对象，且字段名只能用英文：
  opinion（观点正文）, tags（数组）, argument_summary, actionability, quote
- tags 只能从这个固定标签表中选：{tag_list}
- 若某观点确实无法归入上述标签，在 suggested_tags 中写"建议新增：XXX"，但 tags 字段仍从固定表里选最接近的。
- actionability 只能是：{actionability}
- 对于书中需要读者自行判断、不能照搬的地方，在 opinions 里用 actionability="需自己判断" 标出。

示例（仅说明字段，勿照抄内容）：
{{"opinion":"……","tags":["财报分析"],"argument_summary":"……","actionability":"原则","quote":"原文……"}}

章节标题：{chapter.title}

章节正文：
{chapter.text}
"""


def read_chapter(chapter: Chapter) -> ChapterNote:
    data = create_structured(
        _get_client(),
        prompt=_build_prompt(chapter),
        schema=_CHAPTER_SCHEMA,
        max_tokens=config.MAX_TOKENS_PER_CHAPTER,
    )
    data = normalize_chapter_payload(data)

    opinions = [
        OpinionEntry(
            opinion=o["opinion"],
            chapter=chapter.title,
            tags=o["tags"],
            argument_summary=o["argument_summary"],
            actionability=o["actionability"],
            quote=o["quote"],
        )
        for o in data["opinions"]
    ]
    return ChapterNote(
        chapter_index=chapter.index,
        chapter_title=chapter.title,
        core_points=data["core_points"],
        arguments=data["arguments"],
        actionables=data["actionables"],
        quotes=data["quotes"],
        opinions=opinions,
        suggested_tags=data.get("suggested_tags", []),
    )
