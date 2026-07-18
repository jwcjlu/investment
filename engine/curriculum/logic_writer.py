"""课时逻辑结构：placeholder / AI / 磁盘缓存。"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from engine.curriculum.kg_ids import make_edge_id, make_node_id
from engine.curriculum.lesson_id import encode_lesson_id
from engine.curriculum.logic_models import (
    KGEdge,
    KGNode,
    LogicLayer,
    LogicNodeRef,
    LogicStructure,
)
from engine.curriculum.models import Lesson
from engine.llm import create_structured, make_client
from engine.models import ChapterNote, NoteAtom, SourceRef

LOGIC_SCHEMA = {
    "type": "object",
    "properties": {
        "layers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "level": {"type": "integer"},
                    "title": {"type": "string"},
                    "labels": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["level", "title", "labels"],
                "additionalProperties": False,
            },
        },
        "nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "kind": {
                        "type": "string",
                        "enum": ["concept", "claim", "metric", "case"],
                    },
                    "aliases": {"type": "array", "items": {"type": "string"}},
                    "excerpt": {"type": "string"},
                },
                "required": ["label", "kind", "aliases", "excerpt"],
                "additionalProperties": False,
            },
        },
        "edges": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "from_label": {"type": "string"},
                    "to_label": {"type": "string"},
                    "rel": {
                        "type": "string",
                        "enum": ["causes", "contrasts", "defines", "evidenced_by"],
                    },
                    "excerpt": {"type": "string"},
                },
                "required": ["from_label", "to_label", "rel", "excerpt"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["layers", "nodes", "edges"],
    "additionalProperties": False,
}

MAX_TOKENS = 2500


def _logic_path(logic_dir: str, lesson_id: str) -> str:
    return os.path.join(logic_dir, f"{encode_lesson_id(lesson_id)}.json")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _source_from_excerpt(
    lesson: Lesson, excerpt: str
) -> tuple[List[SourceRef], bool]:
    excerpt = (excerpt or "").strip()
    if not excerpt or lesson.chapter_index is None:
        return [], True
    ref = SourceRef(
        book_title=lesson.book_title,
        chapter_index=lesson.chapter_index,
        excerpt=excerpt,
    )
    return [ref], False


def _node_from_label(
    label: str,
    *,
    kind: str,
    lesson: Lesson,
    sources: Optional[List[SourceRef]] = None,
    excerpt: str = "",
    aliases: Optional[List[str]] = None,
) -> KGNode:
    if sources is None:
        sources, ungrounded = _source_from_excerpt(lesson, excerpt)
    else:
        ungrounded = not bool(sources)
    return KGNode(
        node_id=make_node_id(label),
        label=label,
        aliases=list(aliases or []),
        kind=kind,
        sources=list(sources or []),
        ungrounded=ungrounded,
    )


def placeholder_logic(
    lesson: Lesson, note: Optional[ChapterNote] = None
) -> LogicStructure:
    nodes: List[KGNode] = []
    layers: List[LogicLayer] = []

    l1 = _node_from_label(
        lesson.opinion,
        kind="claim",
        lesson=lesson,
        sources=list(lesson.sources or []),
    )
    nodes.append(l1)
    layers.append(
        LogicLayer(level=1, title="结论", items=[LogicNodeRef(node_id=l1.node_id)])
    )

    l2_items: List[LogicNodeRef] = []
    atoms: List[NoteAtom] = list(note.core_points) if note else []
    for atom in atoms[:5]:
        n = _node_from_label(
            atom.text,
            kind="claim",
            lesson=lesson,
            sources=list(atom.sources or []),
        )
        nodes.append(n)
        l2_items.append(LogicNodeRef(node_id=n.node_id))
    if l2_items:
        layers.append(LogicLayer(level=2, title="机制", items=l2_items))

    return LogicStructure(
        lesson_id=lesson.lesson_id,
        layers=layers,
        nodes=nodes,
        edges=[],
        source="placeholder",
        generated_at=_now(),
    )


def save_logic(logic: LogicStructure, logic_dir: str) -> None:
    os.makedirs(logic_dir, exist_ok=True)
    path = _logic_path(logic_dir, logic.lesson_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(logic.to_dict(), f, ensure_ascii=False, indent=2)


def load_logic(lesson_id: str, logic_dir: str) -> Optional[LogicStructure]:
    path = _logic_path(logic_dir, lesson_id)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return LogicStructure.from_dict(json.load(f))


def generate_ai_logic(
    lesson: Lesson, note: Optional[ChapterNote] = None
) -> LogicStructure:
    core = "；".join(a.text for a in (note.core_points if note else [])[:12])
    args = "；".join(a.text for a in (note.arguments if note else [])[:12])
    prompt = f"""你是投资学习教练。根据下面「一则原则课时」整理逻辑结构（分层 + 关系），必须能溯源到摘录。

书名：《{lesson.book_title}》
章节：{lesson.chapter}
原则：{lesson.opinion}
论据摘要：{lesson.argument_summary}
金句：{lesson.quote}
核心观点：{core or "（无）"}
论据：{args or "（无）"}

要求：
- layers：1=结论 2=机制 3=证据；labels 使用 nodes 中出现的 label
- nodes：kind 仅 concept|claim|metric|case；excerpt 为书中支撑短句（可取自金句/要点）
- edges：rel 仅 causes|contrasts|defines|evidenced_by；excerpt 支撑该关系
- 不要编造书中没有的因果；不确定就少画边
"""
    data = create_structured(
        make_client(),
        prompt=prompt,
        schema=LOGIC_SCHEMA,
        max_tokens=MAX_TOKENS,
    )
    return _postprocess_ai_logic(lesson, data)


def _postprocess_ai_logic(lesson: Lesson, data: Dict[str, Any]) -> LogicStructure:
    nodes_by_label: Dict[str, KGNode] = {}
    for raw in data.get("nodes") or []:
        label = (raw.get("label") or "").strip()
        if not label:
            continue
        node = _node_from_label(
            label,
            kind=raw.get("kind") or "claim",
            lesson=lesson,
            excerpt=raw.get("excerpt") or "",
            aliases=list(raw.get("aliases") or []),
        )
        nodes_by_label[label] = node
        nodes_by_label[node.label] = node

    def ensure_label(label: str) -> KGNode:
        label = (label or "").strip()
        if label in nodes_by_label:
            return nodes_by_label[label]
        node = _node_from_label(label, kind="concept", lesson=lesson, excerpt="")
        nodes_by_label[label] = node
        return node

    edges: List[KGEdge] = []
    for raw in data.get("edges") or []:
        frm = ensure_label(raw.get("from_label") or "")
        to = ensure_label(raw.get("to_label") or "")
        if not frm.label or not to.label:
            continue
        sources, ungrounded = _source_from_excerpt(lesson, raw.get("excerpt") or "")
        edges.append(
            KGEdge(
                edge_id=make_edge_id(frm.node_id, raw.get("rel") or "causes", to.node_id),
                from_id=frm.node_id,
                to_id=to.node_id,
                rel=raw.get("rel") or "causes",
                sources=sources,
                ungrounded=ungrounded,
            )
        )

    layers: List[LogicLayer] = []
    for raw in data.get("layers") or []:
        items: List[LogicNodeRef] = []
        for label in raw.get("labels") or []:
            node = ensure_label(label)
            items.append(LogicNodeRef(node_id=node.node_id))
        if items:
            layers.append(
                LogicLayer(
                    level=int(raw.get("level") or 1),
                    title=raw.get("title") or "",
                    items=items,
                )
            )

    if not layers:
        return placeholder_logic(lesson)

    # dedupe nodes by node_id
    uniq: Dict[str, KGNode] = {}
    for n in nodes_by_label.values():
        uniq[n.node_id] = n

    return LogicStructure(
        lesson_id=lesson.lesson_id,
        layers=layers,
        nodes=list(uniq.values()),
        edges=edges,
        source="ai",
        generated_at=_now(),
    )


def get_or_create_logic(
    lesson: Lesson,
    logic_dir: str,
    note: Optional[ChapterNote] = None,
    use_ai: bool = True,
    force: bool = False,
) -> LogicStructure:
    if not force:
        cached = load_logic(lesson.lesson_id, logic_dir)
        if cached is not None:
            return cached

    if use_ai:
        try:
            logic = generate_ai_logic(lesson, note)
            save_logic(logic, logic_dir)
            return logic
        except Exception:
            pass

    logic = placeholder_logic(lesson, note)
    save_logic(logic, logic_dir)
    return logic
