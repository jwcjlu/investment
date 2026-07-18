from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import List, Optional

from engine.models import SourceRef


@dataclass
class LogicNodeRef:
    node_id: str

    def to_dict(self) -> dict:
        return {"node_id": self.node_id}

    @classmethod
    def from_dict(cls, d: dict) -> "LogicNodeRef":
        return cls(node_id=d["node_id"])


@dataclass
class LogicLayer:
    level: int
    title: str
    items: List[LogicNodeRef] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "title": self.title,
            "items": [i.to_dict() for i in self.items],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LogicLayer":
        return cls(
            level=int(d["level"]),
            title=d.get("title") or "",
            items=[LogicNodeRef.from_dict(i) for i in d.get("items") or []],
        )


@dataclass
class KGNode:
    node_id: str
    label: str
    aliases: List[str] = field(default_factory=list)
    kind: str = "claim"
    sources: List[SourceRef] = field(default_factory=list)
    ungrounded: bool = False

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "label": self.label,
            "aliases": list(self.aliases),
            "kind": self.kind,
            "sources": [s.to_dict() for s in self.sources],
            "ungrounded": self.ungrounded,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "KGNode":
        return cls(
            node_id=d["node_id"],
            label=d.get("label") or "",
            aliases=list(d.get("aliases") or []),
            kind=d.get("kind") or "claim",
            sources=[
                SourceRef.from_dict(s) for s in (d.get("sources") or []) if isinstance(s, dict)
            ],
            ungrounded=bool(d.get("ungrounded")),
        )


@dataclass
class KGEdge:
    edge_id: str
    from_id: str
    to_id: str
    rel: str
    sources: List[SourceRef] = field(default_factory=list)
    ungrounded: bool = False

    def to_dict(self) -> dict:
        return {
            "edge_id": self.edge_id,
            "from": self.from_id,
            "to": self.to_id,
            "rel": self.rel,
            "sources": [s.to_dict() for s in self.sources],
            "ungrounded": self.ungrounded,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "KGEdge":
        return cls(
            edge_id=d["edge_id"],
            from_id=d.get("from") or d.get("from_id") or "",
            to_id=d.get("to") or d.get("to_id") or "",
            rel=d.get("rel") or "causes",
            sources=[
                SourceRef.from_dict(s) for s in (d.get("sources") or []) if isinstance(s, dict)
            ],
            ungrounded=bool(d.get("ungrounded")),
        )


@dataclass
class LogicStructure:
    lesson_id: str
    layers: List[LogicLayer]
    nodes: List[KGNode]
    edges: List[KGEdge]
    source: str  # "ai" | "placeholder"
    generated_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "lesson_id": self.lesson_id,
            "layers": [layer.to_dict() for layer in self.layers],
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "source": self.source,
            "generated_at": self.generated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LogicStructure":
        return cls(
            lesson_id=d["lesson_id"],
            layers=[LogicLayer.from_dict(x) for x in d.get("layers") or []],
            nodes=[KGNode.from_dict(x) for x in d.get("nodes") or []],
            edges=[KGEdge.from_dict(x) for x in d.get("edges") or []],
            source=d.get("source") or "placeholder",
            generated_at=d.get("generated_at"),
        )
