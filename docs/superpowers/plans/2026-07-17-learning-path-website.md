# 投资理论知识学习路径网站 Implementation Plan

> **状态：已完成**（2026-07-17，经 subagent-driven-development 实现并合入 main）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 用 FastAPI 本地网站，把子项目 A 的精读缓存（及可选 Notion）重组为「主题模块 + 难度序」课表，支持浏览观点课、展开章节笔记、落盘进度与缓存的 AI 模块导读。

**Architecture:** `engine/curriculum/` 负责加载素材、规则组课、进度与导读；`serve_course.py` 用 FastAPI + Jinja 提供首页/模块页/观点课与进度 API。组课纯规则；AI 仅在生成/重建模块导读时调用，结果缓存到 `curriculum/intros/`。

**Tech Stack:** Python 3.10+（命令 `python`）、FastAPI、uvicorn、Jinja2、复用现有 `engine.models` / `engine.llm` / `config` / `notion-client`、pytest。测试命令：`python -m pytest`。

**Spec:** `docs/superpowers/specs/2026-07-17-learning-path-website-design.md`

---

## 文件结构

```
D:\workspace\investment\
├─ serve_course.py                 # CLI + FastAPI 入口
├─ engine/
│  └─ curriculum/
│     ├─ __init__.py
│     ├─ models.py                 # CatalogItem, Lesson, Module, ModuleIntro, ProgressState
│     ├─ lesson_id.py              # 稳定 lesson id / URL 编解码
│     ├─ loader.py                 # 扫描 output/.cache → CatalogItem + 章节索引
│     ├─ assembler.py              # 按 FIXED_TAGS + 可执行度 → Module[]
│     ├─ progress.py               # curriculum/progress.json
│     ├─ intro_writer.py           # 占位 + AI 导读缓存
│     └─ notion_sync.py            # 可选拉取观点库并合并
├─ templates/
│  ├─ base.html
│  ├─ index.html
│  ├─ module.html
│  └─ lesson.html
├─ static/
│  └─ style.css
├─ curriculum/                     # 运行时生成（gitignore）
│  ├─ progress.json
│  ├─ catalog.json                 # 可选加速启动
│  └─ intros/{tag}.json
└─ tests/
   ├─ fixtures/curriculum_cache/   # 假章节 JSON
   ├─ test_lesson_id.py
   ├─ test_assembler.py
   ├─ test_progress.py
   ├─ test_loader.py
   ├─ test_intro_writer.py
   └─ test_serve_course.py
```

**测试边界：** loader / assembler / progress / lesson_id / intro 占位逻辑离线单测。真实 Anthropic / Notion 不进自动化；intro 的 AI 路径用 monkeypatch。HTTP 用 FastAPI `TestClient` 冒烟。

**gitignore 增量：** 在 `.gitignore` 增加 `curriculum/`（进度与导读属本地状态）。

---

### Task 1: 课程数据模型与 lesson id

**Files:**
- Create: `engine/curriculum/__init__.py`
- Create: `engine/curriculum/models.py`
- Create: `engine/curriculum/lesson_id.py`
- Create: `tests/test_lesson_id.py`
- Modify: `.gitignore`

- [x] **Step 1: 更新 `.gitignore`**

在文件末尾确保有：
```
.superpowers/
curriculum/
```

- [x] **Step 2: 写失败测试 `tests/test_lesson_id.py`**

```python
from engine.curriculum.lesson_id import make_lesson_id, encode_lesson_id, decode_lesson_id


def test_make_lesson_id_stable():
    a = make_lesson_id("聪明的投资者", "第1章", "安全边际是核心")
    b = make_lesson_id("聪明的投资者", "第1章", "安全边际是核心")
    assert a == b
    assert a.startswith("聪明的投资者::第1章::")
    assert len(a.split("::")[-1]) == 12


def test_make_lesson_id_differs_on_opinion():
    a = make_lesson_id("书", "章", "观点甲")
    b = make_lesson_id("书", "章", "观点乙")
    assert a != b


def test_url_roundtrip():
    raw = make_lesson_id("书名", "第2章", "某观点")
    enc = encode_lesson_id(raw)
    assert "/" not in enc and " " not in enc
    assert decode_lesson_id(enc) == raw


def test_tag_roundtrip_with_slash():
    from engine.curriculum.lesson_id import encode_tag, decode_tag
    tag = "护城河/竞争优势"
    enc = encode_tag(tag)
    assert "/" not in enc
    assert decode_tag(enc) == tag
```

- [x] **Step 3: 运行确认失败**

Run: `python -m pytest tests/test_lesson_id.py -v`  
Expected: FAIL（模块不存在）

- [x] **Step 4: 实现**

`engine/curriculum/__init__.py`: 空文件或导出说明。

`engine/curriculum/lesson_id.py`:
```python
from __future__ import annotations
import hashlib
from urllib.parse import quote, unquote


def make_lesson_id(book_title: str, chapter: str, opinion: str) -> str:
    h = hashlib.sha256(opinion.encode("utf-8")).hexdigest()[:12]
    return f"{book_title}::{chapter}::{h}"


def encode_lesson_id(lesson_id: str) -> str:
    return quote(lesson_id, safe="")


def decode_lesson_id(encoded: str) -> str:
    return unquote(encoded)


def encode_tag(tag: str) -> str:
    """URL path segment for tags that may contain '/' (e.g. 护城河/竞争优势)."""
    return quote(tag, safe="")


def decode_tag(encoded: str) -> str:
    return unquote(encoded)
```

`engine/curriculum/models.py`:
```python
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from engine.models import OpinionEntry, ChapterNote


@dataclass
class CatalogItem:
    """带书名的观点 + 可选章节笔记引用。"""
    book_title: str
    opinion: OpinionEntry
    chapter_index: Optional[int] = None  # 用于查章节笔记；Notion-only 可为 None

    def to_dict(self) -> dict:
        return {
            "book_title": self.book_title,
            "opinion": self.opinion.to_dict(),
            "chapter_index": self.chapter_index,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CatalogItem":
        return cls(
            book_title=d["book_title"],
            opinion=OpinionEntry.from_dict(d["opinion"]),
            chapter_index=d.get("chapter_index"),
        )


@dataclass
class Lesson:
    lesson_id: str
    book_title: str
    chapter: str
    chapter_index: Optional[int]
    opinion: str
    argument_summary: str
    actionability: str
    quote: str
    tags: List[str]


@dataclass
class Module:
    tag: str
    lessons: List[Lesson]


@dataclass
class ModuleIntro:
    tag: str
    goals: str
    cross_book: str
    study_order_note: str
    source: str  # "ai" | "placeholder"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ModuleIntro":
        return cls(**d)


@dataclass
class ProgressState:
    completed: List[str] = field(default_factory=list)
    last_lesson_id: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ProgressState":
        return cls(
            completed=list(d.get("completed") or []),
            last_lesson_id=d.get("last_lesson_id"),
            updated_at=d.get("updated_at"),
        )
```

- [x] **Step 5: 运行测试通过**

Run: `python -m pytest tests/test_lesson_id.py -v`  
Expected: PASS

- [x] **Step 6: Commit**

```bash
git add .gitignore engine/curriculum/__init__.py engine/curriculum/models.py engine/curriculum/lesson_id.py tests/test_lesson_id.py
git commit -m "feat(curriculum): add models and stable lesson ids"
```

---

### Task 2: assembler（规则组课）

**Files:**
- Create: `engine/curriculum/assembler.py`
- Create: `tests/test_assembler.py`

- [x] **Step 1: 写失败测试**

```python
from engine.models import OpinionEntry
from engine.curriculum.models import CatalogItem
from engine.curriculum.assembler import assemble_modules
from engine.curriculum.lesson_id import make_lesson_id


def _item(book, chapter, opinion, tags, actionability, idx=1):
    return CatalogItem(
        book_title=book,
        chapter_index=idx,
        opinion=OpinionEntry(
            opinion=opinion,
            chapter=chapter,
            tags=tags,
            argument_summary="论据",
            actionability=actionability,
            quote="金句",
        ),
    )


def test_assemble_groups_by_tag_and_skips_empty():
    items = [
        _item("A书", "第1章", "观点1", ["估值"], "原则"),
        _item("B书", "第2章", "观点2", ["风险控制"], "可直接执行"),
    ]
    modules = assemble_modules(items)
    tags = [m.tag for m in modules]
    assert "估值" in tags
    assert "风险控制" in tags
    assert "复利" not in tags  # 无观点不展示


def test_assemble_difficulty_order():
    items = [
        _item("A", "章", "需判断的", ["估值"], "需自己判断"),
        _item("A", "章", "可执行的", ["估值"], "可直接执行"),
        _item("A", "章", "原则性的", ["估值"], "原则"),
    ]
    mod = next(m for m in assemble_modules(items) if m.tag == "估值")
    assert [l.actionability for l in mod.lessons] == [
        "原则", "可直接执行", "需自己判断"
    ]


def test_multi_tag_appears_in_multiple_modules_same_id():
    items = [_item("A", "章", "跨标签", ["估值", "分散化"], "原则")]
    modules = assemble_modules(items)
    by_tag = {m.tag: m for m in modules}
    id1 = by_tag["估值"].lessons[0].lesson_id
    id2 = by_tag["分散化"].lessons[0].lesson_id
    assert id1 == id2 == make_lesson_id("A", "章", "跨标签")
```

- [x] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_assembler.py -v`  
Expected: FAIL

- [x] **Step 3: 实现 `engine/curriculum/assembler.py`**

```python
from __future__ import annotations
from typing import List, Dict
import config
from engine.curriculum.models import CatalogItem, Lesson, Module
from engine.curriculum.lesson_id import make_lesson_id

_ACTION_ORDER = {name: i for i, name in enumerate(config.ACTIONABILITY_VALUES)}


def _to_lesson(item: CatalogItem) -> Lesson:
    op = item.opinion
    return Lesson(
        lesson_id=make_lesson_id(item.book_title, op.chapter, op.opinion),
        book_title=item.book_title,
        chapter=op.chapter,
        chapter_index=item.chapter_index,
        opinion=op.opinion,
        argument_summary=op.argument_summary,
        actionability=op.actionability,
        quote=op.quote,
        tags=list(op.tags),
    )


def assemble_modules(items: List[CatalogItem]) -> List[Module]:
    buckets: Dict[str, List[Lesson]] = {t: [] for t in config.FIXED_TAGS}
    for item in items:
        lesson = _to_lesson(item)
        for tag in item.opinion.tags:
            if tag in buckets:
                buckets[tag].append(lesson)
    modules: List[Module] = []
    for tag in config.FIXED_TAGS:
        lessons = buckets[tag]
        if not lessons:
            continue
        lessons.sort(
            key=lambda L: (
                _ACTION_ORDER.get(L.actionability, 99),
                L.book_title,
                L.chapter,
                L.opinion,
            )
        )
        modules.append(Module(tag=tag, lessons=lessons))
    return modules
```

- [x] **Step 4: 测试通过并 commit**

Run: `python -m pytest tests/test_assembler.py tests/test_lesson_id.py -v`  
Expected: PASS

```bash
git add engine/curriculum/assembler.py tests/test_assembler.py
git commit -m "feat(curriculum): assemble modules by tag and difficulty"
```

---

### Task 3: progress 落盘

**Files:**
- Create: `engine/curriculum/progress.py`
- Create: `tests/test_progress.py`

- [x] **Step 1: 写失败测试（用 tmp_path）**

```python
import json
from engine.curriculum.progress import load_progress, mark_complete, ProgressStore


def test_mark_complete_dedupes_and_sets_last(tmp_path):
    path = tmp_path / "progress.json"
    store = ProgressStore(str(path))
    store.mark_complete("id-a")
    store.mark_complete("id-a")
    store.mark_complete("id-b")
    state = store.load()
    assert state.completed == ["id-a", "id-b"]
    assert state.last_lesson_id == "id-b"
    assert state.updated_at


def test_corrupt_file_backed_up_and_reset(tmp_path):
    path = tmp_path / "progress.json"
    path.write_text("{not json", encoding="utf-8")
    store = ProgressStore(str(path))
    state = store.load()
    assert state.completed == []
    assert path.with_suffix(".json.bak").exists() or (tmp_path / "progress.json.bak").exists()
```

（实现时 bak 路径定为 `progress.json.bak` 与原文件同目录。）

- [x] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_progress.py -v`

- [x] **Step 3: 实现 `engine/curriculum/progress.py`**

- 默认路径：`curriculum/progress.json`
- `load()`：不存在 → 空状态；JSON 坏 → 改名为 `progress.json.bak` 后返回空状态
- `mark_complete(lesson_id)`：去重追加、更新 `last_lesson_id` 与 ISO `updated_at`、写盘
- 提供模块级函数或 `ProgressStore` 类（测试与上一致即可）

- [x] **Step 4: 测试通过并 commit**

```bash
git add engine/curriculum/progress.py tests/test_progress.py
git commit -m "feat(curriculum): persist learning progress to disk"
```

---

### Task 4: loader（扫描本地 cache）

**Files:**
- Create: `engine/curriculum/loader.py`
- Create: `tests/test_loader.py`
- Create: `tests/fixtures/curriculum_cache/样例书/第1章.json`
- Create: `tests/fixtures/curriculum_cache/坏书/第1章.json`（非法 JSON）

- [x] **Step 1: 写夹具**

`tests/fixtures/curriculum_cache/样例书/第1章.json` — 合法 `ChapterNote.to_dict()`，含至少 1 条带标签 `估值` 的 opinion。

`tests/fixtures/curriculum_cache/坏书/第1章.json`:
```
{not-json
```

- [x] **Step 2: 写失败测试**

```python
from pathlib import Path
from engine.curriculum.loader import load_catalog_from_cache


FIXTURE = Path(__file__).parent / "fixtures" / "curriculum_cache"


def test_load_catalog_reads_opinions(tmp_path):
    # 可直接指向 FIXTURE，或复制到 tmp_path
    items, notes_index, warnings = load_catalog_from_cache(str(FIXTURE))
    assert any(i.book_title == "样例书" for i in items)
    assert any("估值" in i.opinion.tags for i in items)
    key = ("样例书", 1)
    assert key in notes_index


def test_load_skips_corrupt_json():
    items, notes_index, warnings = load_catalog_from_cache(str(FIXTURE))
    assert any("坏书" in w or "第1章" in w for w in warnings)
    assert not any(i.book_title == "坏书" for i in items)
```

- [x] **Step 3: 实现 `load_catalog_from_cache(cache_root: str)`**

逻辑：
1. `cache_root` 下每个子目录 = 书名（与 `engine.cache._cache_dir` 一致，目录名即书名）。
2. 匹配 `第{N}章.json`（可用正则 `^第(\d+)章\.json$`），`ChapterNote.from_dict`。
3. 每个 opinion → `CatalogItem(book_title=目录名, opinion=..., chapter_index=note.chapter_index)`。
4. `notes_index[(book_title, chapter_index)] = ChapterNote`。
5. 解析失败：append warning，continue。
6. 返回 `(items, notes_index, warnings)`。

复用已有模型，不要改 `engine/cache.py` 的写路径语义；可读其 `_safe` 若需要，但扫描时目录名已是落盘名。

- [x] **Step 4: 测试通过并 commit**

```bash
git add engine/curriculum/loader.py tests/test_loader.py tests/fixtures/curriculum_cache
git commit -m "feat(curriculum): load opinions from local chapter cache"
```

---

### Task 5: intro_writer（占位 + 可缓存 AI）

**Files:**
- Create: `engine/curriculum/intro_writer.py`
- Create: `tests/test_intro_writer.py`

- [x] **Step 1: 写失败测试**

```python
from engine.curriculum.models import Lesson, Module, ModuleIntro
from engine.curriculum.intro_writer import placeholder_intro, load_intro, save_intro, get_or_create_intro


def _mod():
    return Module(
        tag="估值",
        lessons=[
            Lesson("id", "书A", "章1", 1, "观点", "论据", "原则", "金句", ["估值"]),
        ],
    )


def test_placeholder_intro_has_tag_and_source():
    intro = placeholder_intro(_mod())
    assert intro.tag == "估值"
    assert intro.source == "placeholder"
    assert intro.goals


def test_save_load_roundtrip(tmp_path):
    intro = placeholder_intro(_mod())
    save_intro(intro, str(tmp_path))
    loaded = load_intro("估值", str(tmp_path))
    assert loaded.goals == intro.goals


def test_get_or_create_uses_cache_without_ai(tmp_path, monkeypatch):
    calls = {"n": 0}

    def boom(*a, **k):
        calls["n"] += 1
        raise AssertionError("should not call AI when cache exists")

    monkeypatch.setattr("engine.curriculum.intro_writer.generate_ai_intro", boom)
    save_intro(placeholder_intro(_mod()), str(tmp_path))
    intro = get_or_create_intro(_mod(), str(tmp_path), use_ai=True)
    assert intro.source in ("placeholder", "ai")
    assert calls["n"] == 0
```

- [x] **Step 2: 实现**

- `placeholder_intro(module)`：用标签名 + 课数 + 涉及书名列表拼短文。
- `save_intro` / `load_intro`：`{intros_dir}/{safe_tag}.json`，`safe_tag = tag.replace("/", "_")`（仅文件名；**HTTP 路由用 `quote`，见 Task 7**）。
- `generate_ai_intro(module)`：用 `engine.llm.create_structured`，schema 含 `goals` / `cross_book` / `study_order_note`；失败向上抛，由 `get_or_create_intro` 捕获后回落占位。
- `get_or_create_intro(module, intros_dir, use_ai=True, force=False)`：
  - 若存在缓存且非 force → 返回缓存
  - 若 use_ai：尝试 AI，成功则 `source=ai` 并保存
  - 否则/失败：占位并保存（失败时也可选择不覆盖已有；首次则写占位）

- [x] **Step 3: 测试通过并 commit**

```bash
git add engine/curriculum/intro_writer.py tests/test_intro_writer.py
git commit -m "feat(curriculum): module intros with cache and AI fallback"
```

---

### Task 6: Notion sync（可选合并）

**Files:**
- Create: `engine/curriculum/notion_sync.py`
- Create: `tests/test_notion_sync.py`

- [x] **Step 1: 写失败测试（mock client）**

测试 **`merge_catalog(local_items, remote_items) -> List[CatalogItem]`**（名称固定，勿另起 `merge_notion_opinions`）：
- 本地已有相同「书名+章节+观点」→ 保留本地（含 chapter_index）
- Notion 独有 → 追加，`chapter_index=None`

用纯函数 + 假 `CatalogItem`，不打真实 API。另测 `rows_to_catalog_items(notion_pages)` / `fetch_notion_opinion_rows(client, database_id)`。

**查询 API（必须与仓库一致，勿用已弃用的 `databases.query`）：**
- 复用 `engine.notion_writer.resolve_data_source_id(client, database_id)`
- 分页调用 `client.data_sources.query(data_source_id=..., page_size=100, start_cursor=...)`（无 filter = 拉全库）
- mock 时 mock `resolve_data_source_id` + `client.data_sources.query` 返回两页 `results`

Notion 属性名与 A 一致。`rows_to_catalog_items` 需做 `build_opinion_properties` 的逆操作：
- `title` → `properties["观点"]["title"][0]["plain_text"]`（缺省空串）
- `rich_text` → 拼接 `plain_text`（来源书/章节/论据摘要/原文金句）
- `multi_select` → `[x["name"] for x in ...]`
- `select` → `properties["可执行度"]["select"]["name"]`（可为 None 时跳过该行或标「原则」）

- [x] **Step 2: 实现 `notion_sync.py`**

- `fetch_notion_opinion_rows`：如上 `data_sources.query` 分页
- `rows_to_catalog_items` → `CatalogItem`（chapter_index=None）
- `merge_catalog(local, remote)` 按键去重
- 提供 `sync_and_merge(local_items, client, db_id) -> List[CatalogItem]`；CLI 接入在 Task 7，且 **sync 异常由 CLI 捕获后降级**

- [x] **Step 3: 测试通过并 commit**

```bash
git add engine/curriculum/notion_sync.py tests/test_notion_sync.py
git commit -m "feat(curriculum): merge Notion opinions into catalog"
```

---

### Task 7: FastAPI 应用与模板（核心页面）

**Files:**
- Create: `serve_course.py`
- Create: `templates/base.html`
- Create: `templates/index.html`
- Create: `templates/module.html`
- Create: `templates/lesson.html`
- Create: `static/style.css`
- Create: `tests/test_serve_course.py`
- Modify: `requirements.txt`

- [x] **Step 1: 更新依赖**

`requirements.txt` 追加：
```
fastapi>=0.115
uvicorn>=0.32
jinja2>=3.1
httpx>=0.27
```

Run: `pip install fastapi uvicorn jinja2 httpx`

- [x] **Step 2: 写 HTTP 冒烟测试（用夹具 cache，禁 AI）**

```python
from pathlib import Path
from fastapi.testclient import TestClient
from serve_course import create_app
from engine.curriculum.lesson_id import encode_lesson_id


FIXTURE = Path(__file__).parent / "fixtures" / "curriculum_cache"


def test_index_ok_with_fixture_cache(tmp_path):
    app = create_app(
        cache_root=str(FIXTURE),
        curriculum_dir=str(tmp_path / "curriculum"),
        enable_ai_intro=False,
    )
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert "估值" in r.text or "学习" in r.text


def test_empty_cache_friendly_message(tmp_path):
    empty = tmp_path / "cache"
    empty.mkdir()
    app = create_app(
        cache_root=str(empty),
        curriculum_dir=str(tmp_path / "cur"),
        enable_ai_intro=False,
    )
    r = TestClient(app).get("/")
    assert r.status_code == 200
    assert "read_book" in r.text or "精读" in r.text
```

另加：带 `tag` 的模块页 200；`POST /api/progress/complete` 后首页或 API 含该 id；若夹具含 `护城河/竞争优势` 类标签则用 **编码后的 tag** 访问模块页。

- [x] **Step 3: 实现 `create_app` + 路由**

**Tag URL 规则（必做）：** `FIXED_TAGS` 含 `护城河/竞争优势`、`交易成本/税费`。路由使用编码 tag，与 lesson id 相同风格：
- `encode_tag(tag) = urllib.parse.quote(tag, safe="")`
- `decode_tag(encoded) = urllib.parse.unquote(encoded)`
- 路由写成 `GET /module/{encoded_tag}`，模板里所有模块链接走 `encode_tag`
- intro 落盘文件名继续用 `safe_tag`（把 `/` 换成 `_`），与 URL 编码是两套规则，勿混用

路由清单：
- `GET /`：`assemble_modules` + progress 统计；无模块时显示引导文案；**「继续上次」**：若 `last_lesson_id` 有值，链到对应 lesson（需能反查所属模块 tag：取该 lesson 的 `tags[0]` 或在模块列表中搜索含该 id 的第一个模块），文案如「继续上次学习」
- 首页模块卡片附带**难度跨度**：该模块 lessons 的 actionability 按 `ACTIONABILITY_VALUES` 取最低～最高，展示如 `原则 → 需自己判断`（仅一种时只显示该档）
- `GET /module/{encoded_tag}`：解码 tag → 课表 + `get_or_create_intro(..., use_ai=enable_ai_intro)`
- `GET /lesson/{encoded_id}?tag=<encoded_tag>`：解码 id 与 tag，找 lesson；`expand=1` 时从 notes_index 取章节；下一课 = **当前 tag 模块**内下一则；链接用 `encode_lesson_id` / `encode_tag`
- `POST /api/progress/complete`：JSON `{"lesson_id": "..."}`（原始 id，非 URL 编码）→ mark_complete → 204/200
- `GET /api/progress`：返回 progress JSON

启动时加载 catalog 一次（挂 `app.state`）。**MVP 不实现 `catalog.json` 读写加速**（YAGNI；`--sync-notion` 只合并进内存再启动即可）。改 `output/.cache` 后需重启服务——写进 README。

模板：简洁中文排版；`base.html` 提供导航；CSS 白底深字、可读行宽即可（非营销页）。

- [x] **Step 4: CLI**

`serve_course.py`：
```python
# argparse:
# --host 127.0.0.1 --port 8765
# --cache-root output/.cache
# --curriculum-dir curriculum
# --sync-notion
# --rebuild-intros
# --no-ai-intro
```

- `--sync-notion`：`load_dotenv` 后尝试拉 Notion 并 `merge_catalog`；**失败时打印错误到 stderr，不退出进程，继续仅用本地 cache 启动**（与 spec 错误处理一致）。成功则打印合并后观点数。
- `--rebuild-intros`：对每个非空模块 `force=True` 重建导读；可与服务器同开（启动前重建）或单独跑完退出——实现选「启动前重建再 listen」即可
- 默认：`uvicorn.run(app, host=..., port=...)`

- [x] **Step 5: 测试通过并 commit**

```bash
git add serve_course.py templates static requirements.txt tests/test_serve_course.py
git commit -m "feat: add FastAPI learning path site"
```

---

### Task 8: README 与手动验收清单

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-07-17-learning-path-website-design.md`（状态改为已实现计划就绪 / 实现中，可选）

- [x] **Step 1: README 增加「学习路径网站」一节**

说明：
```bash
pip install -r requirements.txt
python serve_course.py
# 浏览器打开 http://127.0.0.1:8765

python serve_course.py --sync-notion
python serve_course.py --rebuild-intros
python serve_course.py --no-ai-intro
```

前置：至少一本 `python read_book.py ...` 产生的 `output/.cache`。

- [x] **Step 2: 本地手动冒烟（有真实缓存时）**

1. `python serve_course.py --no-ai-intro`
2. 打开首页，看到多个主题模块
3. 进入「财报分析」或「估值」，课表按原则→可执行→需判断
4. 打开一课，展开章节笔记，标记已学，点下一课
5. 重启服务，进度仍在

- [x] **Step 3: 跑全量测试**

Run: `python -m pytest -v`  
Expected: 全部 PASS（含既有 A 测试）

- [x] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document learning path website usage"
```

---

## 实现注意（给执行者）

1. **Windows / PowerShell**：提交信息用 `git commit -m "..." -m "..."`，不要用 bash heredoc。
2. **不要改**子项目 A 的精读 prompt；缺口只加 curriculum 层。
3. **URL**：lesson 路径必须用 `encode_lesson_id`，否则中文 `::` 会坏。
4. **下一课**：必须带当前 `tag` 查询参数，在该模块 `lessons` 列表中找下一则。
5. **YAGNI**：不做自测题、登录、公网部署、精美前端框架。

---

## 完成定义

- [x] 上述 Task 1–8 完成，pytest 全绿
- [x] `python serve_course.py --no-ai-intro` 可在有缓存时浏览模块与观点课
- [x] 进度写入 `curriculum/progress.json` 且损坏可恢复
- [x] README 含启动说明
