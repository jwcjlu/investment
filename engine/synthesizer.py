from __future__ import annotations
import json
from typing import List, Tuple
from anthropic import Anthropic
from engine.models import ChapterNote, BookSummary, OpinionEntry
import config

_client = Anthropic()

_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "one_liner": {"type": "string"},
        "core_theses": {"type": "array", "items": {"type": "string"}},
        "principles": {"type": "array", "items": {"type": "string"}},
        "open_questions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["one_liner", "core_theses", "principles", "open_questions"],
    "additionalProperties": False,
}


def _digest(notes: List[ChapterNote]) -> str:
    parts = []
    for n in sorted(notes, key=lambda x: x.chapter_index):
        parts.append(f"【{n.chapter_title}】")
        parts.append("核心观点：" + "；".join(n.core_points))
        parts.append("可执行要点：" + "；".join(n.actionables))
    return "\n".join(parts)


def synthesize(book_title: str, author: str,
               notes: List[ChapterNote]) -> Tuple[BookSummary, List[OpinionEntry]]:
    prompt = f"""下面是《{book_title}》（作者：{author}）各章的精读笔记摘要。
请据此产出全书层面的总结，帮助读者建立投资体系。

要求：
- one_liner：一句话总结全书。
- core_theses：全书 3-5 条核心论点。
- principles：提炼成可执行的投资原则/清单（读者能照着做的）。
- open_questions：书中需要读者自己判断、不能照搬的关键点。

各章摘要：
{_digest(notes)}
"""
    resp = _client.messages.create(
        model=config.MODEL,
        max_tokens=config.MAX_TOKENS_SYNTHESIS,
        thinking={"type": "adaptive"},
        output_config={"format": {"type": "json_schema", "schema": _SUMMARY_SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    )
    text = next(b.text for b in resp.content if b.type == "text")
    data = json.loads(text)

    summary = BookSummary(
        book_title=book_title,
        author=author,
        one_liner=data["one_liner"],
        core_theses=data["core_theses"],
        principles=data["principles"],
        open_questions=data["open_questions"],
    )

    # 观点条目直接汇总各章 opinions（合成阶段不重新调模型，忠于逐章产出）
    opinions: List[OpinionEntry] = []
    for n in sorted(notes, key=lambda x: x.chapter_index):
        opinions.extend(n.opinions)

    return summary, opinions
