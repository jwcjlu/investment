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
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import config
from engine.curriculum.assembler import assemble_modules
from engine.curriculum.daily import add_more, load_or_create_daily
from engine.curriculum.intro_writer import get_or_create_intro
from engine.curriculum.lesson_id import (
    decode_lesson_id,
    decode_tag,
    encode_lesson_id,
    encode_tag,
)
from engine.curriculum.loader import load_catalog_from_cache
from engine.curriculum.models import CatalogItem, Lesson, Module, ProgressState
from engine.curriculum.progress import ProgressStore
from engine.curriculum.quiz_writer import get_or_create_quiz, grade, load_quiz
from engine.curriculum.logic_writer import get_or_create_logic
from engine.cache import load_chapter_text_from_cache_root
from engine.source_locate import locate_excerpt, slice_window

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
SPA_DIR = os.path.join(STATIC_DIR, "spa")

templates = Jinja2Templates(directory=TEMPLATES_DIR)


class CompleteRequest(BaseModel):
    lesson_id: str


class QuizSubmitRequest(BaseModel):
    tag: str
    answers: Dict[str, int]


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


def _lesson_brief(lesson: Lesson, completed: set) -> dict:
    return {
        "lesson_id": lesson.lesson_id,
        "encoded_id": encode_lesson_id(lesson.lesson_id),
        "opinion": lesson.opinion,
        "book_title": lesson.book_title,
        "chapter": lesson.chapter,
        "actionability": lesson.actionability,
        "completed": lesson.lesson_id in completed,
    }


def _build_module_cards(modules: List[Module], completed: set) -> List[dict]:
    return [
        {
            "tag": m.tag,
            "encoded_tag": encode_tag(m.tag),
            "count": len(m.lessons),
            "difficulty": _difficulty_span(m),
            "done_count": sum(1 for l in m.lessons if l.lesson_id in completed),
        }
        for m in modules
    ]


def _build_continue_lesson(
    modules: List[Module], progress: ProgressState
) -> Optional[dict]:
    if not progress.last_lesson_id:
        return None
    target_module = _find_module_for_lesson(modules, progress.last_lesson_id)
    if target_module is None:
        return None
    lesson = next(
        l for l in target_module.lessons if l.lesson_id == progress.last_lesson_id
    )
    return {
        "opinion": lesson.opinion,
        "encoded_id": encode_lesson_id(lesson.lesson_id),
        "encoded_tag": encode_tag(target_module.tag),
    }


def _daily_response(modules: List[Module], state: dict, progress: ProgressState) -> dict:
    completed = set(progress.completed)
    tag = state.get("tag")
    lessons: List[dict] = []
    if tag:
        module = next((m for m in modules if m.tag == tag), None)
        if module is not None:
            lesson_map = {l.lesson_id: l for l in module.lessons}
            lessons = [
                _lesson_brief(lesson_map[lid], completed)
                for lid in state.get("lesson_ids") or []
                if lid in lesson_map
            ]
    return {
        "date": state.get("date"),
        "tag": tag,
        "encoded_tag": encode_tag(tag) if tag else None,
        "extra_batches": state.get("extra_batches", 0),
        "lesson_ids": list(state.get("lesson_ids") or []),
        "lessons": lessons,
    }


def create_app(
    cache_root: str = "output/.cache",
    curriculum_dir: str = "curriculum",
    enable_ai_intro: bool = True,
    catalog_items: Optional[List[CatalogItem]] = None,
    serve_spa: Optional[bool] = None,
) -> FastAPI:
    """构建并初始化 FastAPI 应用：启动时一次性加载课表到 app.state。

    serve_spa:
      None  — 若 static/spa/index.html 存在则托管 SPA，否则用 Jinja 页面
      True  — 强制 SPA（缺构建产物则 503）
      False — 强制 Jinja（测试用）
    """
    local_items, notes_index, warnings = load_catalog_from_cache(cache_root)
    items = catalog_items if catalog_items is not None else local_items
    modules = assemble_modules(items)

    intros_dir = os.path.join(curriculum_dir, "intros")
    quizzes_dir = os.path.join(curriculum_dir, "quizzes")
    logic_dir = os.path.join(curriculum_dir, "logic")
    progress_path = os.path.join(curriculum_dir, "progress.json")
    daily_path = os.path.join(curriculum_dir, "daily.json")

    spa_index = os.path.join(SPA_DIR, "index.html")
    if serve_spa is None:
        use_spa = os.path.isfile(spa_index)
    else:
        use_spa = serve_spa

    app = FastAPI(title="投资学习路径")
    app.state.modules = modules
    app.state.notes_index = notes_index
    app.state.warnings = warnings
    app.state.progress_store = ProgressStore(progress_path)
    app.state.intros_dir = intros_dir
    app.state.quizzes_dir = quizzes_dir
    app.state.logic_dir = logic_dir
    app.state.cache_root = cache_root
    app.state.daily_path = daily_path
    app.state.enable_ai_intro = enable_ai_intro
    app.state.use_spa = use_spa

    if os.path.isdir(STATIC_DIR):
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    if not use_spa:

        @app.get("/")
        def index(request: Request):
            modules = app.state.modules
            progress = app.state.progress_store.load()
            completed = set(progress.completed)

            module_cards = _build_module_cards(modules, completed)
            continue_lesson = _build_continue_lesson(modules, progress)

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

        # `:path` (not the default str converter, which excludes '/') is required because
        # ASGI servers decode %2F to '/' before route matching, and tags like
        # "护城河/竞争优势" produce an encoded_tag containing '/'.
        @app.get("/module/{encoded_tag:path}")
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

            lessons = [_lesson_brief(lesson, completed) for lesson in module.lessons]

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
            next_lesson = (
                module.lessons[idx + 1] if idx + 1 < len(module.lessons) else None
            )

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

    @app.post("/api/progress")
    def post_progress(payload: CompleteRequest):
        app.state.progress_store.mark_complete(payload.lesson_id)
        return {"ok": True}

    @app.get("/api/modules")
    def api_modules():
        modules = app.state.modules
        progress = app.state.progress_store.load()
        completed = set(progress.completed)
        return {
            "modules": _build_module_cards(modules, completed),
            "completed_count": len(completed),
            "continue_lesson": _build_continue_lesson(modules, progress),
        }

    @app.get("/api/modules/{encoded_tag:path}")
    def api_module_detail(encoded_tag: str):
        tag = decode_tag(encoded_tag)
        module = next((m for m in app.state.modules if m.tag == tag), None)
        if module is None:
            raise HTTPException(status_code=404, detail="模块不存在")

        intro = get_or_create_intro(
            module, app.state.intros_dir, use_ai=app.state.enable_ai_intro
        )
        progress = app.state.progress_store.load()
        completed = set(progress.completed)

        return {
            "tag": tag,
            "encoded_tag": encode_tag(tag),
            "intro": intro.to_dict(),
            "lessons": [_lesson_brief(lesson, completed) for lesson in module.lessons],
        }

    @app.get("/api/lessons/{encoded_id}")
    def api_lesson_detail(
        encoded_id: str,
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
        if bool(expand) and expand != "0":
            note = app.state.notes_index.get((lesson.book_title, lesson.chapter_index))
            if note is not None:
                chapter_note = note.to_dict()

        progress = app.state.progress_store.load()
        completed = lesson.lesson_id in progress.completed

        return {
            "lesson_id": lesson.lesson_id,
            "encoded_id": encode_lesson_id(lesson.lesson_id),
            "tag": module_tag,
            "encoded_tag": encode_tag(module_tag),
            "book_title": lesson.book_title,
            "chapter": lesson.chapter,
            "chapter_index": lesson.chapter_index,
            "opinion": lesson.opinion,
            "argument_summary": lesson.argument_summary,
            "actionability": lesson.actionability,
            "quote": lesson.quote,
            "sources": [s.to_dict() for s in (lesson.sources or [])],
            "completed": completed,
            "chapter_note": chapter_note,
            "next_lesson_id": next_lesson.lesson_id if next_lesson else None,
            "next_encoded_id": encode_lesson_id(next_lesson.lesson_id)
            if next_lesson
            else None,
        }

    @app.get("/api/lessons/{encoded_id}/logic")
    def api_lesson_logic(
        encoded_id: str,
        tag: str,
        force: bool = False,
    ):
        lesson_id = decode_lesson_id(encoded_id)
        module_tag = decode_tag(tag)
        module = next((m for m in app.state.modules if m.tag == module_tag), None)
        if module is None:
            raise HTTPException(status_code=404, detail="模块不存在")
        lesson = next((l for l in module.lessons if l.lesson_id == lesson_id), None)
        if lesson is None:
            raise HTTPException(status_code=404, detail="课程不存在")
        note = None
        if lesson.chapter_index is not None:
            note = app.state.notes_index.get((lesson.book_title, lesson.chapter_index))
        logic = get_or_create_logic(
            lesson,
            app.state.logic_dir,
            note=note,
            use_ai=app.state.enable_ai_intro,
            force=force,
        )
        return logic.to_dict()

    @app.get("/api/source")
    def api_source(
        book: str,
        chapter: int,
        start: Optional[int] = None,
        end: Optional[int] = None,
        excerpt: Optional[str] = None,
    ):
        note = app.state.notes_index.get((book, chapter))
        chapter_title = note.chapter_title if note else f"第{chapter}章"
        chapter_text = load_chapter_text_from_cache_root(
            app.state.cache_root, book, chapter
        )
        degraded = False
        highlight = None
        text = ""

        if not chapter_text:
            degraded = True
            text = (excerpt or "")[:4000]
            return {
                "book_title": book,
                "chapter_index": chapter,
                "chapter_title": chapter_title,
                "text": text,
                "highlight": None,
                "excerpt": excerpt,
                "degraded": True,
            }

        char_start, char_end = start, end
        if char_start is None or char_end is None:
            if excerpt:
                char_start, char_end = locate_excerpt(chapter_text, excerpt)
            if char_start is None:
                degraded = True

        text, highlight = slice_window(
            chapter_text,
            char_start,
            char_end,
            excerpt=excerpt,
            pad=800,
            hard_max=4000,
        )
        if highlight is None and excerpt:
            degraded = True

        return {
            "book_title": book,
            "chapter_index": chapter,
            "chapter_title": chapter_title,
            "text": text,
            "highlight": {"start": highlight[0], "end": highlight[1]}
            if highlight
            else None,
            "excerpt": excerpt,
            "degraded": degraded,
        }

    @app.get("/api/daily")
    def api_daily(tag: Optional[str] = None):
        progress = app.state.progress_store.load()
        preferred_tag = decode_tag(tag) if tag else None
        state = load_or_create_daily(
            app.state.daily_path,
            app.state.modules,
            progress,
            preferred_tag=preferred_tag,
        )
        return _daily_response(app.state.modules, state, progress)

    @app.post("/api/daily/more")
    def api_daily_more():
        progress = app.state.progress_store.load()
        state, added = add_more(app.state.daily_path, app.state.modules, progress)
        response = _daily_response(app.state.modules, state, progress)
        response["added"] = added
        return response

    @app.get("/api/quiz")
    def api_quiz(
        tag: Optional[str] = None,
        daily: bool = False,
        force: bool = False,
    ):
        if daily:
            progress = app.state.progress_store.load()
            state = load_or_create_daily(
                app.state.daily_path, app.state.modules, progress
            )
            module_tag = state.get("tag")
            if not module_tag:
                raise HTTPException(status_code=404, detail="今日暂无焦点模块")
        elif tag:
            module_tag = decode_tag(tag)
        else:
            raise HTTPException(status_code=400, detail="需提供 tag 或 daily=1")

        module = next((m for m in app.state.modules if m.tag == module_tag), None)
        if module is None:
            raise HTTPException(status_code=404, detail="模块不存在")

        quiz = get_or_create_quiz(
            module,
            app.state.quizzes_dir,
            use_ai=app.state.enable_ai_intro,
            force=force,
        )
        return {**quiz, "encoded_tag": encode_tag(module.tag)}

    @app.post("/api/quiz/submit")
    def api_quiz_submit(payload: QuizSubmitRequest):
        quiz = load_quiz(payload.tag, app.state.quizzes_dir)
        if quiz is None:
            raise HTTPException(status_code=404, detail="题库不存在，请先获取测验")
        return grade(quiz, payload.answers)

    if use_spa:
        spa_assets = os.path.join(SPA_DIR, "assets")
        if os.path.isdir(spa_assets):
            app.mount(
                "/assets",
                StaticFiles(directory=spa_assets),
                name="spa-assets",
            )

        @app.get("/")
        def spa_root():
            if not os.path.isfile(spa_index):
                raise HTTPException(
                    status_code=503,
                    detail="SPA 未构建：请先执行 cd web && npm run build",
                )
            return FileResponse(spa_index)

        @app.get("/{full_path:path}")
        def spa_fallback(full_path: str):
            if not os.path.isfile(spa_index):
                raise HTTPException(
                    status_code=503,
                    detail="SPA 未构建：请先执行 cd web && npm run build",
                )
            # 已注册的 /api、/static、/assets 优先；其余交给 SPA history fallback
            candidate = os.path.normpath(os.path.join(SPA_DIR, full_path))
            if candidate.startswith(SPA_DIR) and os.path.isfile(candidate):
                return FileResponse(candidate)
            return FileResponse(spa_index)

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
    ap.add_argument("--rebuild-quizzes", action="store_true", help="启动前强制重建各模块测验题")
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

    if args.rebuild_quizzes:
        for module in app.state.modules:
            get_or_create_quiz(
                module, app.state.quizzes_dir, use_ai=enable_ai_intro, force=True
            )
        print(f"已重建 {len(app.state.modules)} 个模块的测验题。", file=sys.stderr)

    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
