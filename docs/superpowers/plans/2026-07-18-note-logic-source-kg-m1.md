# Note Logic · Source Index · KG Subgraph (M1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** M1 — 精读笔记带 `SourceRef`、课时页展示分层+关系子图、侧栏抽屉回原文；全局 `node_id` 从第一天按稳定算法生成（为 M2/M3 铺路）。

**Architecture:** 沿用 intro/quiz 模式：`logic_writer` 按需 AI 生成并缓存到 `curriculum/logic/`；`SourceRef` 经 `NoteAtom` 嵌入章节 JSON（旧字符串 normalize 兼容）；章文本按需切片供 `/api/source`；SPA 课时页渲染逻辑结构 + `SourceDrawer`。

**Tech Stack:** Python 3 + FastAPI、现有 `engine.llm` / pytest；Vite + React + TypeScript SPA（`web/`）。

**Spec:** `docs/superpowers/specs/2026-07-18-note-logic-source-kg-design.md`  
**Out of this plan:** M2 模块聚合图、M3 全局图谱页（另写计划）。

---

## File map

| File | Responsibility |
|---|---|
| `engine/models.py` | `SourceRef`, `NoteAtom`；`OpinionEntry.sources`；`ChapterNote` 列表字段改为 `List[NoteAtom]` |
| `engine/source_locate.py` | excerpt 规范化匹配 → `char_start/end`；章内窗口切片 |
| `engine/curriculum/kg_ids.py` | `canonical_label`、`make_node_id`、`make_edge_id`；读 `curriculum/kg_aliases.json` |
| `engine/curriculum/logic_models.py` | `KGNode`/`KGEdge`/`LogicStructure` dataclass + ser/de |
| `engine/curriculum/logic_writer.py` | placeholder / AI / cache get_or_create（对齐 `intro_writer`） |
| `engine/reader.py` | schema + normalize NoteAtom；精读后调用 locate |
| `engine/curriculum/models.py` / `assembler.py` | `Lesson` 增加 `sources: List[SourceRef]`（来自 OpinionEntry） |
| `serve_course.py` | `GET .../logic`、`GET /api/source`；lesson API 返回 `sources` + NoteAtom 形 `chapter_note` |
| `web/src/components/SourceDrawer.tsx` | 侧栏原文 |
| `web/src/components/LogicPanel.tsx` | 分层 + 简易关系图 |
| `web/src/pages/LessonPage.tsx` | 接入上述组件 |
| `web/src/api.ts` | `getLogic` / `getSource` |
| `tests/test_source_locate.py` 等 | TDD 覆盖 |

---

### Task 1: SourceRef + NoteAtom models & normalize

**Files:**
- Modify: `engine/models.py`
- Create: `tests/test_note_atom.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_note_atom.py
from engine.models import NoteAtom, SourceRef, OpinionEntry, ChapterNote


def test_note_atom_from_plain_string():
    atom = NoteAtom.from_any("护城河很重要")
    assert atom.text == "护城河很重要"
    assert atom.sources == []


def test_chapter_note_loads_legacy_string_lists():
    note = ChapterNote.from_dict(
        {
            "chapter_index": 1,
            "chapter_title": "第1章",
            "core_points": ["a"],
            "arguments": ["b"],
            "actionables": ["c"],
            "quotes": ["q"],
            "opinions": [
                {
                    "opinion": "原则",
                    "chapter": "第1章",
                    "tags": ["估值"],
                    "argument_summary": "论据",
                    "actionability": "原则",
                    "quote": "金句",
                }
            ],
        }
    )
    assert note.core_points[0].text == "a"
    assert note.opinions[0].sources == []


def test_opinion_roundtrip_with_sources():
    op = OpinionEntry(
        opinion="原则",
        chapter="第1章",
        tags=["估值"],
        argument_summary="论据",
        actionability="原则",
        quote="金句",
        sources=[
            SourceRef(
                book_title="书",
                chapter_index=1,
                excerpt="金句",
                char_start=10,
                char_end=12,
            )
        ],
    )
    restored = OpinionEntry.from_dict(op.to_dict())
    assert restored.sources[0].excerpt == "金句"
    assert restored.sources[0].char_start == 10
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_note_atom.py -v`  
Expected: FAIL (ImportError / missing types)

- [ ] **Step 3: Implement models**

In `engine/models.py`:

```python
@dataclass
class SourceRef:
    book_title: str
    chapter_index: int
    excerpt: str
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    para_id: Optional[str] = None

    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, d: dict) -> "SourceRef": ...


@dataclass
class NoteAtom:
    text: str
    sources: List[SourceRef] = field(default_factory=list)

    @classmethod
    def from_any(cls, raw: Any) -> "NoteAtom":
        if isinstance(raw, str):
            return cls(text=raw.strip(), sources=[])
        if isinstance(raw, dict):
            text = str(raw.get("text") or "").strip()
            sources = [SourceRef.from_dict(s) for s in (raw.get("sources") or [])]
            return cls(text=text, sources=sources)
        return cls(text=str(raw).strip(), sources=[])
```

- Update `OpinionEntry` with `sources: List[SourceRef] = field(default_factory=list)`；`from_dict` 缺省 `[]`。  
- Update `ChapterNote` fields to `List[NoteAtom]`；`from_dict` 用 `NoteAtom.from_any`。  
- Fix any broken callers that assume `List[str]`（`engine/cache.py`、`notion_writer.py`、`synthesizer.py`、tests）：展示处用 `.text`。

- [ ] **Step 4: Run tests + full related suite**

Run: `pytest tests/test_note_atom.py tests/test_models.py tests/test_normalize_opinion.py tests/test_cache.py -v`  
Expected: PASS（先修编译/断言至绿）

- [ ] **Step 5: Commit**

```bash
git add engine/models.py tests/test_note_atom.py engine/cache.py engine/notion_writer.py engine/synthesizer.py tests/
git commit -m "feat(models): NoteAtom and SourceRef with legacy string normalize"
```

---

### Task 2: Excerpt locate helpers

**Files:**
- Create: `engine/source_locate.py`
- Create: `tests/test_source_locate.py`

- [ ] **Step 1: Write failing tests**

```python
from engine.source_locate import locate_excerpt, slice_window


def test_locate_excerpt_finds_offsets():
    chapter = "前文。" + "投资资本回报率与成本之差" + "。后文。"
    start, end = locate_excerpt(chapter, "投资资本回报率与成本之差")
    assert start is not None and chapter[start:end] == "投资资本回报率与成本之差"


def test_locate_excerpt_normalizes_whitespace():
    chapter = "回报率  与成本"
    start, end = locate_excerpt(chapter, "回报率 与成本")
    assert start is not None


def test_locate_miss_returns_none():
    assert locate_excerpt("abc", "zzz") == (None, None)


def test_slice_window_includes_highlight():
    text = "a" * 100 + "TARGET" + "b" * 100
    start, end = 100, 106
    window, hi = slice_window(text, start, end, pad=20, hard_max=4000)
    assert "TARGET" in window
    assert hi is not None
    assert window[hi[0] : hi[1]] == "TARGET"
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/test_source_locate.py -v`

- [ ] **Step 3: Implement `engine/source_locate.py`**

```python
def _norm(s: str) -> str:
    # NFKC + collapse whitespace
    ...

def locate_excerpt(chapter_text: str, excerpt: str) -> tuple[Optional[int], Optional[int]]:
    """Return char_start/end in original chapter_text, or (None, None)."""
    ...

def slice_window(
    chapter_text: str,
    char_start: Optional[int],
    char_end: Optional[int],
    *,
    excerpt: Optional[str] = None,
    pad: int = 800,
    hard_max: int = 4000,
) -> tuple[str, Optional[tuple[int, int]]]:
    """Return (window_text, highlight_relative_or_None)."""
    ...
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add engine/source_locate.py tests/test_source_locate.py
git commit -m "feat: locate excerpts in chapter text for SourceRef offsets"
```

---

### Task 3: Stable KG ids

**Files:**
- Create: `engine/curriculum/kg_ids.py`
- Create: `curriculum/kg_aliases.json`（可先 `{}`）
- Create: `tests/test_kg_ids.py`

- [ ] **Step 1: Failing tests**

```python
from engine.curriculum.kg_ids import make_node_id, make_edge_id, canonical_label


def test_node_id_stable_and_alias_aware(tmp_path, monkeypatch):
    alias_path = tmp_path / "kg_aliases.json"
    alias_path.write_text('{"ROIC": "投资资本回报率"}', encoding="utf-8")
    monkeypatch.setenv("KG_ALIASES_PATH", str(alias_path))  # or pass path arg
    a = make_node_id("ROIC", aliases_path=str(alias_path))
    b = make_node_id("投资资本回报率", aliases_path=str(alias_path))
    assert a == b
    assert a.startswith("n_")


def test_edge_id_stable():
    e1 = make_edge_id("n_aaa", "causes", "n_bbb")
    e2 = make_edge_id("n_aaa", "causes", "n_bbb")
    assert e1 == e2 and e1.startswith("e_")
```

Prefer **function arg** `aliases_path` with default `curriculum/kg_aliases.json` over env（更简单）。

- [ ] **Step 2–4: Implement + green + commit**

```bash
git commit -m "feat(curriculum): stable node_id and edge_id for KG"
```

---

### Task 4: logic_writer (placeholder + cache)

**Files:**
- Create: `engine/curriculum/logic_models.py`
- Create: `engine/curriculum/logic_writer.py`
- Create: `tests/test_logic_writer.py`
- Reference: `engine/curriculum/intro_writer.py`, `engine/curriculum/quiz_writer.py`

- [ ] **Step 1: Failing tests for placeholder + cache**

```python
def test_placeholder_logic_layers_from_lesson_and_note(tmp_path):
    # Build a Lesson + ChapterNote with NoteAtoms
    logic = placeholder_logic(lesson, note)
    assert logic.source == "placeholder"
    assert logic.edges == []
    assert logic.layers[0].level == 1
    assert any(n.label == lesson.opinion for n in logic.nodes)
    # L1 grounded if opinion.sources non-empty


def test_get_or_create_uses_cache(tmp_path, monkeypatch):
    calls = {"n": 0}

    def boom(*a, **k):
        calls["n"] += 1
        raise RuntimeError("should not be called when cache hit")

    monkeypatch.setattr("engine.curriculum.logic_writer.generate_ai_logic", boom)
    logic_dir = tmp_path / "logic"
    first = get_or_create_logic(lesson, note, str(logic_dir), use_ai=False)
    second = get_or_create_logic(lesson, note, str(logic_dir), use_ai=True)
    assert first.to_dict() == second.to_dict()
    assert calls["n"] == 0
```

- [ ] **Step 2: Implement models + `placeholder_logic` + `save/load` + `get_or_create_logic`**

Mirror quiz_writer:

- cache path: `os.path.join(logic_dir, f"{encode_lesson_id(lesson.lesson_id)}.json")`（与 URL 编码一致，避免特殊字符）  
- `create_app`：`app.state.logic_dir = os.path.join(curriculum_dir, "logic")`（对齐 intros/quizzes）  
- 无 `chapter_note` 或 `chapter_index is None`：placeholder 仅用 `lesson.opinion` 作 L1，L2 空  

- `get_or_create_logic(lesson, note, logic_dir, use_ai=True, force=False)`  
- AI path stub: raise / skip until Task 5；Task 4 可只实现 placeholder 分支让 `use_ai=False` 绿

- [ ] **Step 3: Tests PASS with `use_ai=False`**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(curriculum): placeholder logic_structure cache"
```

---

### Task 5: AI logic generation + postprocess ids/sources

**Files:**
- Modify: `engine/curriculum/logic_writer.py`
- Modify: `tests/test_logic_writer.py`

- [ ] **Step 1: Test AI happy path with monkeypatch**

```python
def test_generate_ai_logic_assigns_stable_ids(monkeypatch):
    monkeypatch.setattr(
        "engine.curriculum.logic_writer.create_structured",
        lambda *a, **k: {
            "layers": [{"level": 1, "title": "结论", "labels": ["价值创造"]}],
            "nodes": [
                {"label": "价值创造", "kind": "claim", "aliases": [], "excerpt": "……"}
            ],
            "edges": [
                {"from_label": "ROIC", "to_label": "价值创造", "rel": "causes", "excerpt": "……"}
            ],
        },
    )
    # also provide ROIC node in fixture or let postprocess create from edge endpoints
    logic = generate_ai_logic(lesson, note, book_title=lesson.book_title)
    assert all(n.node_id.startswith("n_") for n in logic.nodes)
    assert logic.source == "ai"
```

- [ ] **Step 2: Implement prompt + schema + postprocess**

- AI 只输出 label/kind/aliases/rel/excerpt（不要 node_id）  
- 后处理：`make_node_id` / `make_edge_id`；用 excerpt 建 `SourceRef`；无 excerpt → `ungrounded=True`  
- layers items → `LogicNodeRef(node_id=...)`  
- `get_or_create_logic`：AI 失败 → placeholder（同 intro）

- [ ] **Step 3: Green + commit**

```bash
git commit -m "feat(curriculum): AI logic_structure with grounded sources"
```

---

### Task 6: Reader schema + locate on read

**Files:**
- Modify: `engine/reader.py`
- Modify: `tests/test_normalize_opinion.py`（及新测）
- Optional: keep LLM schema items as strings for M1 **if** post-pass wraps them — **preferred M1:** schema 仍用 string[]，`normalize_chapter_payload` 包成 NoteAtom，并用章文本+quote/core 文本启发式填 excerpt（模型暂不强制输出 sources，降低 prompt 风险）

**Spec alignment note for implementer:** Spec 最终要模型输出 excerpt；M1 可分两步——先启发式（quote / 要点文本作 excerpt + locate），再升级 schema。本 Task 实现：

1. normalize 列表 → NoteAtom  
2. 对每个 atom/opinion：若 `sources` 空且有可用 excerpt 候选，构造 `SourceRef(book, chapter_index, excerpt)` 并 `locate_excerpt` 填偏移  

- [ ] **Step 1: Test normalize wraps + locate fills offsets when chapter text provided**

- [ ] **Step 2: Implement in `normalize_chapter_payload` / `read_chapter` 出口**

- [ ] **Step 3: Green + commit**

```bash
git commit -m "feat(reader): attach SourceRef excerpts and offsets to note atoms"
```

---

### Task 7: FastAPI `/api/source` + `/api/lessons/.../logic`

**Files:**
- Modify: `serve_course.py`
- Create: `engine/curriculum/chapter_text.py`（从 ebook 路径或测试夹具取章文本；M1 最小：`app.state` 可注入 `chapter_text_loader`，测试用 dict）
- Modify: `tests/test_api_ux.py` 或 Create: `tests/test_api_logic_source.py`

- [ ] **Step 1: Failing API tests**（`serve_spa=False`）

```python
def test_api_source_returns_window(tmp_path):
    # create_app with injected chapter texts
    r = client.get("/api/source", params={
        "book": "Fixture Book",
        "chapter": 1,
        "excerpt": "估值很重要",
    })
    assert r.status_code == 200
    body = r.json()
    assert "text" in body and "highlight" in body


def test_api_logic_placeholder(tmp_path):
    r = client.get(f"/api/lessons/{encode_lesson_id(lesson_id)}/logic", params={"tag": encode_tag("估值")})
    assert r.status_code == 200
    assert r.json()["source"] in ("placeholder", "ai")
    assert "layers" in r.json()
```

- [ ] **Step 2: Lesson.sources + API routes**

- `Lesson` 增加 `sources: List[SourceRef]`；`assembler` 从 `OpinionEntry.sources` 拷贝  
- `GET /api/lessons/{id}` JSON **必须**含 `sources`（原则级）以及 `chapter_note` 内 NoteAtom（`text`/`sources`）  
- 测试断言：`r.json()["sources"]` 为 list；旧夹具无 sources 时为 `[]`  
- `GET /api/source` — 按 spec 响应形；`chapter_title` 优先从 `notes_index[(book, chapter)].chapter_title` 取，缺省 `第{n}章`；找不到章文本时仍 200 + `degraded=true`（仅 excerpt），书名完全未知可 404  
- 无偏移：调用 `slice_window(..., excerpt=excerpt)` 在窗口内二次匹配填 `highlight`  
- `GET /api/lessons/{encoded_id}/logic?tag=&force=` — `get_or_create_logic`；AI 开关 **复用** `enable_ai_intro`

- [ ] **Step 3: Chapter text loading**

M1 策略（写死）：

1. 若 `output/.cache/{book}/_chapters/{index}.txt` 存在则读（Task 6 可选写入）  
2. 否则 `degraded=true`，`text` 尽量用 excerpt，`highlight=null`  
3. 测试夹具写入 `_chapters` 文件

- [ ] **Step 4: Green + commit**

```bash
git commit -m "feat(api): lesson logic and source window endpoints"
```

---

### Task 8: SPA LogicPanel + SourceDrawer

**Files:**
- Create: `web/src/components/LogicPanel.tsx`
- Create: `web/src/components/SourceDrawer.tsx`
- Modify: `web/src/api.ts`
- Modify: `web/src/pages/LessonPage.tsx`
- Modify: `web/src/App.css`

- [ ] **Step 1: Add API clients + TS types**

```ts
export type SourceRef = {
  book_title: string
  chapter_index: number
  excerpt: string
  char_start?: number | null
  char_end?: number | null
}
export type NoteAtom = { text: string; sources: SourceRef[] }
export type LogicStructure = {
  layers: { level: number; title: string; items: { node_id: string }[] }[]
  nodes: {
    node_id: string
    label: string
    sources: SourceRef[]
    ungrounded?: boolean
  }[]
  edges: { edge_id: string; from: string; to: string; rel: string }[]
  source: string
}
// ChapterNote.core_points/arguments/actionables/quotes: NoteAtom[]（不再是 string[]）
export function getLessonLogic(encodedId: string, encodedTag: string, force = false)
export function getSource(params: {
  book: string
  chapter: number
  start?: number
  end?: number
  excerpt?: string
})
```

- [ ] **Step 2: LogicPanel**

- 位置：原则 meta **之后**、论据摘要 **之前**  
- 左分层 / 右简易节点+边列表（纯 CSS）  
- `edges.length === 0` 时右侧显示「暂无关系图」  
- **点击节点**（非 ungrounded 且 `sources[0]` 存在）→ 调用同一 `onOpenSource(sources[0])` 打开抽屉（满足「节点可点出 SourceRef」）

- [ ] **Step 3: SourceDrawer** — fixed 右侧栏；打开时 fetch source；高亮 `<mark>`

- [ ] **Step 4: LessonPage**

- 挂载 LogicPanel + SourceDrawer  
- 列表渲染用 `atom.text`；`atom.sources[0]` 旁「原文」按钮  
- 原则标题旁：若 `lesson.sources?.length` 显示「原文」  
- 金句：若 `lesson.sources` 中 excerpt 对齐 quote，或 chapter_note.quotes 带 sources，同样显示按钮

- [ ] **Step 5: `cd web && npm run build`** Expected: success

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(web): lesson logic panel and source drawer"
```

---

### Task 9: README + smoke + M1 acceptance

**Files:**
- Modify: `README.md`（简短说明 logic/原文）
- Modify: spec status line optional

- [ ] **Step 1: Update README** — 提及课时逻辑结构与原文侧栏；旧缓存无索引则无按钮

- [ ] **Step 2: Run full tests**

```bash
pytest tests/test_note_atom.py tests/test_source_locate.py tests/test_kg_ids.py tests/test_logic_writer.py tests/test_api_logic_source.py tests/test_api_ux.py -v
cd web && npm run build
```

Expected: all PASS / build OK

- [ ] **Step 3: Manual smoke**（真实缓存可选）

```bash
python serve_course.py --no-ai-intro --cache-root output/.cache
# 打开一课：见分层；点原文（若有 sources）
```

- [ ] **Step 4: Commit**

```bash
git commit -m "docs: document M1 logic structure and source drawer"
```

---

## M1 acceptance checklist (from spec)

- [ ] 新精读路径能产生带 excerpt/偏移的 SourceRef（或启发式等价）  
- [ ] 课时页分层 + 子图；placeholder 无边；空图显示「暂无关系图」  
- [ ] **逻辑节点可点击**打开 SourceDrawer（有 SourceRef 时）  
- [ ] 原则/原始要点「原文」按钮可用（API 暴露 `lesson.sources` + NoteAtom.sources）  
- [ ] 原文侧栏高亮；无偏移 degraded  
- [ ] logic 磁盘缓存 + AI 失败降级  
- [ ] 旧缓存无 SourceRef 不崩溃  

## Follow-ups (not this plan)

- M2: `GET /api/modules/{tag}/kg` + 模块页图  
- M3: `/kg` 全局页  
- 精读 schema 强制模型输出 NoteAtom.sources  
- 保存 `_chapters/*.txt` 于精读时  

---

## Execution note

Prefer @superpowers:subagent-driven-development. TDD per task. Do not start M2 until M1 checklist is green.
