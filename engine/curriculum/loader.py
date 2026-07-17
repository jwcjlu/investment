from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Tuple

from engine.curriculum.models import CatalogItem
from engine.models import ChapterNote

_CHAPTER_FILE_RE = re.compile(r"^第(\d+)章\.json$")


def load_catalog_from_cache(
    cache_root: str,
) -> Tuple[List[CatalogItem], Dict[Tuple[str, int], ChapterNote], List[str]]:
    items: List[CatalogItem] = []
    notes_index: Dict[Tuple[str, int], ChapterNote] = {}
    warnings: List[str] = []

    if not os.path.isdir(cache_root):
        return items, notes_index, warnings

    for book_title in sorted(os.listdir(cache_root)):
        book_dir = os.path.join(cache_root, book_title)
        if not os.path.isdir(book_dir):
            continue

        for filename in sorted(os.listdir(book_dir)):
            match = _CHAPTER_FILE_RE.match(filename)
            if not match:
                continue

            path = os.path.join(book_dir, filename)
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                note = ChapterNote.from_dict(data)
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                warnings.append(f"跳过 {book_title}/{filename}: {exc}")
                continue

            notes_index[(book_title, note.chapter_index)] = note
            for opinion in note.opinions:
                items.append(
                    CatalogItem(
                        book_title=book_title,
                        opinion=opinion,
                        chapter_index=note.chapter_index,
                    )
                )

    return items, notes_index, warnings
