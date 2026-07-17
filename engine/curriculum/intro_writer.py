from __future__ import annotations

import json
import os
from typing import Optional

from engine.curriculum.models import Module, ModuleIntro
from engine.llm import create_structured, make_client

INTRO_SCHEMA = {
    "type": "object",
    "properties": {
        "goals": {"type": "string"},
        "cross_book": {"type": "string"},
        "study_order_note": {"type": "string"},
    },
    "required": ["goals", "cross_book", "study_order_note"],
    "additionalProperties": False,
}

MAX_TOKENS = 2000


def _safe_tag(tag: str) -> str:
    return tag.replace("/", "_")


def _intro_path(intros_dir: str, tag: str) -> str:
    return os.path.join(intros_dir, f"{_safe_tag(tag)}.json")


def placeholder_intro(module: Module) -> ModuleIntro:
    n = len(module.lessons)
    books = sorted({lesson.book_title for lesson in module.lessons})
    books_str = "、".join(books) if books else "（暂无）"
    return ModuleIntro(
        tag=module.tag,
        goals=f"本模块围绕「{module.tag}」主题，共 {n} 则观点，帮助你建立系统性认识。",
        cross_book=f"涉及书目：{books_str}。",
        study_order_note="建议按列表顺序学习：先原则，再可直接执行，最后需自己判断。",
        source="placeholder",
    )


def save_intro(intro: ModuleIntro, intros_dir: str) -> None:
    os.makedirs(intros_dir, exist_ok=True)
    path = _intro_path(intros_dir, intro.tag)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(intro.to_dict(), f, ensure_ascii=False, indent=2)


def load_intro(tag: str, intros_dir: str) -> Optional[ModuleIntro]:
    path = _intro_path(intros_dir, tag)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return ModuleIntro.from_dict(data)


def _build_prompt(module: Module) -> str:
    lines = [
        f"请为投资学习路径中的「{module.tag}」主题模块撰写导读。",
        f"该模块共 {len(module.lessons)} 则观点，来源如下：",
        "",
    ]
    for i, lesson in enumerate(module.lessons, 1):
        lines.append(
            f"{i}. 《{lesson.book_title}》{lesson.chapter} — {lesson.opinion}"
            f"（可执行度：{lesson.actionability}）"
        )
    lines.extend([
        "",
        "请输出 JSON，包含：",
        "- goals：模块学习目标（2-4 句）",
        "- cross_book：跨书对照要点（不同书对同一主题的差异或互补）",
        "- study_order_note：学习顺序建议（结合可执行度排序：原则→可直接执行→需自己判断）",
    ])
    return "\n".join(lines)


def generate_ai_intro(module: Module) -> ModuleIntro:
    client = make_client()
    data = create_structured(
        client,
        prompt=_build_prompt(module),
        schema=INTRO_SCHEMA,
        max_tokens=MAX_TOKENS,
    )
    return ModuleIntro(
        tag=module.tag,
        goals=data["goals"],
        cross_book=data["cross_book"],
        study_order_note=data["study_order_note"],
        source="ai",
    )


def get_or_create_intro(
    module: Module,
    intros_dir: str,
    use_ai: bool = True,
    force: bool = False,
) -> ModuleIntro:
    if not force:
        cached = load_intro(module.tag, intros_dir)
        if cached is not None:
            return cached

    if use_ai:
        try:
            intro = generate_ai_intro(module)
            save_intro(intro, intros_dir)
            return intro
        except Exception:
            pass

    intro = placeholder_intro(module)
    save_intro(intro, intros_dir)
    return intro
