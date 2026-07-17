from __future__ import annotations

import json
import os
from datetime import date
from typing import List, Optional

import config
from engine.curriculum.models import Module, ProgressState

PRINCIPLE = "原则"


def _today_str(today: Optional[date] = None) -> str:
    return (today or date.today()).isoformat()


def _module_map(modules: List[Module]) -> dict[str, Module]:
    return {m.tag: m for m in modules}


def _find_module(modules: List[Module], tag: str) -> Optional[Module]:
    return _module_map(modules).get(tag)


def _principle_lesson_ids(
    module: Module,
    progress: ProgressState,
    exclude: set[str] | None = None,
) -> list[str]:
    skip = set(progress.completed)
    if exclude:
        skip |= exclude
    return [
        lesson.lesson_id
        for lesson in module.lessons
        if lesson.actionability == PRINCIPLE and lesson.lesson_id not in skip
    ]


def _build_daily_list(
    module: Module,
    progress: ProgressState,
    limit: int | None = None,
    exclude: set[str] | None = None,
) -> list[str]:
    cap = limit if limit is not None else config.DAILY_LESSON_LIMIT
    return _principle_lesson_ids(module, progress, exclude)[:cap]


def resolve_focus_tag(
    modules: List[Module],
    progress: ProgressState,
    preferred_tag: str | None = None,
) -> str | None:
    if preferred_tag is not None:
        return preferred_tag

    by_tag = _module_map(modules)

    if progress.last_lesson_id:
        for tag in config.FIXED_TAGS:
            mod = by_tag.get(tag)
            if mod and any(
                lesson.lesson_id == progress.last_lesson_id for lesson in mod.lessons
            ):
                return tag

    for tag in config.FIXED_TAGS:
        mod = by_tag.get(tag)
        if mod and _principle_lesson_ids(mod, progress):
            return tag

    return None


def _load_daily_raw(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _save_daily(path: str, state: dict) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _rebuild_daily(
    modules: List[Module],
    progress: ProgressState,
    preferred_tag: str | None,
    today_str: str,
) -> dict:
    tag = resolve_focus_tag(modules, progress, preferred_tag)
    lesson_ids: list[str] = []
    if tag:
        mod = _find_module(modules, tag)
        if mod:
            lesson_ids = _build_daily_list(mod, progress)
    return {
        "date": today_str,
        "tag": tag,
        "lesson_ids": lesson_ids,
        "extra_batches": 0,
    }


def load_or_create_daily(
    path: str,
    modules: List[Module],
    progress: ProgressState,
    preferred_tag: str | None = None,
    today: date | None = None,
) -> dict:
    today_str = _today_str(today)
    stored = _load_daily_raw(path)

    if stored is None:
        state = _rebuild_daily(modules, progress, preferred_tag, today_str)
        _save_daily(path, state)
        return state

    if stored.get("date") != today_str:
        state = _rebuild_daily(modules, progress, preferred_tag, today_str)
        _save_daily(path, state)
        return state

    if preferred_tag is not None and stored.get("tag") != preferred_tag:
        state = _rebuild_daily(modules, progress, preferred_tag, today_str)
        _save_daily(path, state)
        return state

    return stored


def add_more(
    path: str,
    modules: List[Module],
    progress: ProgressState,
    limit: int | None = None,
) -> tuple[dict, int]:
    state = load_or_create_daily(path, modules, progress)
    tag = state.get("tag")
    if not tag:
        return state, 0

    mod = _find_module(modules, tag)
    if not mod:
        return state, 0

    cap = limit if limit is not None else config.DAILY_LESSON_LIMIT
    existing = set(state.get("lesson_ids") or [])
    to_add = _build_daily_list(mod, progress, limit=cap, exclude=existing)
    added = len(to_add)
    if added == 0:
        return state, 0

    state = {
        **state,
        "lesson_ids": list(state.get("lesson_ids") or []) + to_add,
        "extra_batches": int(state.get("extra_batches") or 0) + 1,
    }
    _save_daily(path, state)
    return state, added
