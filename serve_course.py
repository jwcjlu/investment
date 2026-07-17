"""FastAPI 学习路径网站：把精读缓存重组为主题模块课表。

用法：
    python serve_course.py
    python serve_course.py --sync-notion
    python serve_course.py --rebuild-intros
    python serve_course.py --no-ai-intro
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import config
from engine.curriculum.assembler import assemble_modules
from engine.curriculum.intro_writer import get_or_create_intro
from engine.curriculum.lesson_id import (
    decode_lesson_id,
    decode_tag,
    encode_lesson_id,
    encode_tag,
)
from engine.curriculum.loader import load_catalog_from_cache
from engine.curriculum.models import CatalogItem, Module
from engine.curriculum.progress import ProgressStore

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

templates = Jinja2Templates(directory=TEMPLATES_DIR)


class CompleteRequest(BaseModel):
    lesson_id: str


def _difficulty_span(module: Module) -> str:
    order = config.ACTIONABILITY_VALUES
    present = [v for v in order if any(l.actionability == v for l in module.lessons)]
    if not present:
        return ""
    if len(present) == 1:
        return present[0]
    return f"{present[0]} → {present[-1]}"


def _find_module_for_lesson(modules: List[Module], lesson_id: str) -> Optional[Module]:
    for module in modules:
        for lesson in module.lessons:
            if lesson.lesson_id == lesson_id:
                return module
    return None


def create_app(
    cache_root: str = "output/.cache",
    curriculum_dir: str = "curriculum",
    enable_ai_intro: bool = True,
    catalog_items: Optional[List[CatalogItem]] = None,
) -> FastAPI:
    """构建并初始化 FastAPI 应用：启动时一次性加载课表到 app.state。"""
    local_items, notes_index, warnings = load_catalog_from_cache(cache_root)
    items = catalog_items if catalog_items is not None else local_items
    modules = assemble_modules(items)

    intros_dir = os.path.join(curriculum_dir, "intros")
    progress_path = os.path.join(curriculum_dir, "progress.json")

    app = FastAPI(title="投资学习路径")
    app.state.modules = modules
    app.state.notes_index = notes_index
    app.state.warnings = warnings
    app.state.progress_store = ProgressStore(progress_path)
    app.state.intros_dir = intros_dir
    app.state.enable_ai_intro = enable_ai_intro

    if os.path.isdir(STATIC_DIR):
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    def index(request: Request):
        modules = app.state.modules
        progress = app.state.progress_store.load()
        completed = set(progress.completed)

        module_cards = [
            {
                "tag": m.tag,
                "encoded_tag": encode_tag(m.tag),
                "count": len(m.lessons),
                "difficulty": _difficulty_span(m),
                "done_count": sum(1 for l in m.lessons if l.lesson_id in completed),
            }
            for m in modules
        ]

        continue_lesson = None
        if progress.last_lesson_id:
            target_module = _find_module_for_lesson(modules, progress.last_lesson_id)
            if target_module is not None:
                lesson = next(
                    l for l in target_module.lessons
                    if l.lesson_id == progress.last_lesson_id
                )
                continue_lesson = {
                    "opinion": lesson.opinion,
                    "encoded_id": encode_lesson_id(lesson.lesson_id),
                    "encoded_tag": encode_tag(target_module.tag),
                }

        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "has_modules": len(modules) > 0,
                "modules": module_cards,
                "completed_count": len(completed),
                "continue_lesson": continue_lesson,
            },
        )

    @app.get("/module/{encoded_tag}")
    def module_page(encoded_tag: str, request: Request):
        tag = decode_tag(encoded_tag)
        module = next((m for m in app.state.modules if m.tag == tag), None)
        if module is None:
            raise HTTPException(status_code=404, detail="模块不存在")

        intro = get_or_create_intro(
            module, app.state.intros_dir, use_ai=app.state.enable_ai_intro
        )
        progress = app.state.progress_store.load()
        completed = set(progress.completed)

        lessons = [
            {
                "lesson_id": lesson.lesson_id,
                "encoded_id": encode_lesson_id(lesson.lesson_id),
                "opinion": lesson.opinion,
                "book_title": lesson.book_title,
                "chapter": lesson.chapter,
                "actionability": lesson.actionability,
                "completed": lesson.lesson_id in completed,
            }
            for lesson in module.lessons
        ]

        return templates.TemplateResponse(
            request,
            "module.html",
            {
                "tag": tag,
                "encoded_tag": encoded_tag,
                "intro": intro,
                "lessons": lessons,
            },
        )

    @app.get("/lesson/{encoded_id}")
    def lesson_page(
        encoded_id: str,
        request: Request,
        tag: str,
        expand: Optional[str] = None,
    ):
        lesson_id = decode_lesson_id(encoded_id)
        module_tag = decode_tag(tag)
        module = next((m for m in app.state.modules if m.tag == module_tag), None)
        if module is None:
            raise HTTPException(status_code=404, detail="模块不存在")

        idx = next(
            (i for i, l in enumerate(module.lessons) if l.lesson_id == lesson_id),
            None,
        )
        if idx is None:
            raise HTTPException(status_code=404, detail="课程不存在")

        lesson = module.lessons[idx]
        next_lesson = module.lessons[idx + 1] if idx + 1 < len(module.lessons) else None

        chapter_note = None
        expanded = bool(expand) and expand != "0"
        if expanded:
            chapter_note = app.state.notes_index.get(
                (lesson.book_title, lesson.chapter_index)
            )

        progress = app.state.progress_store.load()
        completed = lesson.lesson_id in progress.completed

        return templates.TemplateResponse(
            request,
            "lesson.html",
            {
                "lesson": lesson,
                "tag": module_tag,
                "encoded_tag": tag,
                "encoded_id": encoded_id,
                "expanded": expanded,
                "chapter_note": chapter_note,
                "next_lesson": next_lesson,
                "next_encoded_id": encode_lesson_id(next_lesson.lesson_id)
                if next_lesson
                else None,
                "completed": completed,
            },
        )

    @app.post("/api/progress/complete")
    def complete_lesson(payload: CompleteRequest):
        app.state.progress_store.mark_complete(payload.lesson_id)
        return {"ok": True}

    @app.get("/api/progress")
    def get_progress():
        return app.state.progress_store.load().to_dict()

    return app


def _try_sync_notion(cache_root: str) -> Optional[List[CatalogItem]]:
    """尝试从 Notion 拉取观点并与本地缓存合并；任何失败都仅打印到 stderr，不抛出。"""
    try:
        from dotenv import load_dotenv
        from notion_client import Client as NotionClient
        from engine.curriculum.notion_sync import sync_and_merge

        load_dotenv()
        token = os.environ["NOTION_TOKEN"]
        db_id = os.environ["NOTION_OPINIONS_DATABASE_ID"]
        client = NotionClient(auth=token)
        local_items, _, _ = load_catalog_from_cache(cache_root)
        merged = sync_and_merge(local_items, client, db_id)
        print(f"Notion 同步完成，合并后共 {len(merged)} 条观点。", file=sys.stderr)
        return merged
    except Exception as exc:  # noqa: BLE001 - 同步失败要降级，不能让 CLI 退出
        print(f"Notion 同步失败，将仅使用本地缓存启动：{exc}", file=sys.stderr)
        return None


def main() -> None:
    ap = argparse.ArgumentParser(description="投资学习路径网站")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--cache-root", default="output/.cache")
    ap.add_argument("--curriculum-dir", default="curriculum")
    ap.add_argument("--sync-notion", action="store_true", help="启动前尝试合并 Notion 观点库")
    ap.add_argument("--rebuild-intros", action="store_true", help="启动前强制重建各模块导读")
    ap.add_argument("--no-ai-intro", action="store_true", help="模块导读只用占位文案，不调用 AI")
    args = ap.parse_args()

    catalog_items: Optional[List[CatalogItem]] = None
    if args.sync_notion:
        catalog_items = _try_sync_notion(args.cache_root)

    enable_ai_intro = not args.no_ai_intro
    app = create_app(
        cache_root=args.cache_root,
        curriculum_dir=args.curriculum_dir,
        enable_ai_intro=enable_ai_intro,
        catalog_items=catalog_items,
    )

    if args.rebuild_intros:
        for module in app.state.modules:
            get_or_create_intro(
                module, app.state.intros_dir, use_ai=enable_ai_intro, force=True
            )
        print(f"已重建 {len(app.state.modules)} 个模块的导读。", file=sys.stderr)

    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
