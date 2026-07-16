from __future__ import annotations
import json
from anthropic import Anthropic
from engine.models import Chapter, ChapterNote, OpinionEntry
import config

_client = Anthropic()  # 从环境变量 ANTHROPIC_API_KEY 读取

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


def _build_prompt(chapter: Chapter) -> str:
    tag_list = "、".join(config.FIXED_TAGS)
    actionability = "、".join(config.ACTIONABILITY_VALUES)
    return f"""你是一位严谨的投资书籍精读助手。请精读下面这一章，提炼结构化笔记。

要求：
- 忠于原文，不臆造。金句必须是原文引用。
- opinions（核心观点）中每条的 tags 只能从这个固定标签表中选：{tag_list}
- 若某观点确实无法归入上述标签，在 suggested_tags 中写"建议新增：XXX"，但 tags 字段仍从固定表里选最接近的。
- actionability 只能是：{actionability}
- 对于书中需要读者自行判断、不能照搬的地方，在 opinions 里用 actionability="需自己判断" 标出。

章节标题：{chapter.title}

章节正文：
{chapter.text}
"""


def read_chapter(chapter: Chapter) -> ChapterNote:
    resp = _client.messages.create(
        model=config.MODEL,
        max_tokens=config.MAX_TOKENS_PER_CHAPTER,
        thinking={"type": "adaptive"},
        output_config={"format": {"type": "json_schema", "schema": _CHAPTER_SCHEMA}},
        messages=[{"role": "user", "content": _build_prompt(chapter)}],
    )
    text = next(b.text for b in resp.content if b.type == "text")
    data = json.loads(text)

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
