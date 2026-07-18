"""全局稳定的 KG node_id / edge_id。"""

from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from functools import lru_cache
from typing import Dict, Optional

_DEFAULT_ALIASES = os.path.join(
    os.path.dirname(__file__), "kg_aliases.json"
)


@lru_cache(maxsize=8)
def _load_aliases(path: str) -> Dict[str, str]:
    if not path or not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items()}


def normalize_label(label: str) -> str:
    s = unicodedata.normalize("NFKC", label or "")
    s = re.sub(r"\s+", " ", s).strip()
    return s.casefold()


def canonical_label(label: str, aliases_path: Optional[str] = None) -> str:
    path = aliases_path or _DEFAULT_ALIASES
    aliases = _load_aliases(path)
    raw = (label or "").strip()
    # alias keys match after light strip; values are canonical display names
    mapped = aliases.get(raw, aliases.get(normalize_label(raw), raw))
    # also try original key casefold against alias keys
    if mapped == raw:
        for k, v in aliases.items():
            if normalize_label(k) == normalize_label(raw):
                mapped = v
                break
    return mapped


def make_node_id(label: str, aliases_path: Optional[str] = None) -> str:
    canon = canonical_label(label, aliases_path=aliases_path)
    digest = hashlib.sha1(normalize_label(canon).encode("utf-8")).hexdigest()[:12]
    return f"n_{digest}"


def make_edge_id(from_id: str, rel: str, to_id: str) -> str:
    payload = f"{from_id}|{rel}|{to_id}"
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]
    return f"e_{digest}"
