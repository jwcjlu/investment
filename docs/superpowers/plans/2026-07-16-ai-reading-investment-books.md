# AI 精读投资书籍 → Notion 笔记引擎 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个 Python 命令行工具，把电子书（EPUB/PDF/TXT）逐章喂给 Claude Opus 4.8 精读，产出结构化笔记，写入 Notion 的总览页面与可跨书检索的观点数据库，并在本地留 Markdown 备份。

**Architecture:** 四个单一职责模块——解析器（切章）、精读器（单章→Opus→JSON 笔记）、合成器（全书笔记→总览+观点条目）、Notion 写入器——由 `read_book.py` 编排。每章笔记边读边缓存到本地 `.cache/`，支持断点续跑；Notion 写入是最后一步且可单独重跑（`push_to_notion.py`）。

**Tech Stack:** Python 3.10（命令 `python`）、`anthropic` SDK（模型 `claude-opus-4-8`，结构化输出用 `output_config.format`）、`ebooklib` + `beautifulsoup4`（EPUB）、`pypdf`（PDF）、`notion-client`、`python-dotenv`、`pytest`。

**环境事实（已核实）：** 目录 `D:\workspace\investment` 当前不是 git 仓库；`python --version` = 3.10.6；`python3` 不存在，用 `python`；`pip` 可用。测试命令统一用 `python -m pytest`。

---

## 文件结构

```
D:\workspace\investment\
├─ .env                       # ANTHROPIC_API_KEY, NOTION_TOKEN（用户填，git 忽略）
├─ .env.example               # 模板
├─ .gitignore
├─ requirements.txt
├─ config.py                  # 固定标签表、模型名、成本阈值、Notion ID
├─ read_book.py               # 主编排 CLI：解析→精读→合成→写Notion→备份
├─ push_to_notion.py          # 单独重跑 Notion 写入（读本地缓存）
├─ engine/
│  ├─ __init__.py
│  ├─ models.py               # 数据类：Chapter, ChapterNote, BookSummary, OpinionEntry
│  ├─ parser.py               # 解析器：书文件 → [Chapter]
│  ├─ reader.py               # 精读器：Chapter → ChapterNote（调 Opus）
│  ├─ synthesizer.py          # 合成器：[ChapterNote] → (BookSummary, [OpinionEntry])
│  ├─ notion_writer.py        # Notion 写入器
│  ├─ cost.py                 # token 估算 + 成本护栏
│  └─ cache.py                # 本地缓存读写 + Markdown 备份
├─ tests/
│  ├─ __init__.py
│  ├─ fixtures/
│  │  ├─ sample.txt           # 测试用小书
│  │  └─ sample.epub          # 测试用小 EPUB（Task 4 生成）
│  ├─ test_parser.py
│  ├─ test_models.py
│  ├─ test_cache.py
│  ├─ test_cost.py
│  └─ test_notion_writer.py
└─ output/
   ├─ .cache/<书名>/第N章.json  # 断点续跑缓存
   └─ <书名>.md                # Markdown 备份
```

**测试边界：** 解析器、models、cache、cost、notion_writer（用 mock）可离线单测，不烧 API。精读器/合成器（真实调 Opus）不写自动化单测，改由端到端人工验收（Task 12）——避免测试烧钱且质量需人眼判断。

---

## Task 1: 项目骨架与 git 初始化

**Files:**
- Create: `D:\workspace\investment\.gitignore`
- Create: `D:\workspace\investment\.env.example`
- Create: `D:\workspace\investment\requirements.txt`
- Create: `D:\workspace\investment\engine\__init__.py`
- Create: `D:\workspace\investment\tests\__init__.py`

- [ ] **Step 1: 初始化 git 仓库**

Run:
```bash
cd "D:/workspace/investment" && git init && git branch -M main
```
Expected: `Initialized empty Git repository ...`

- [ ] **Step 2: 写 `.gitignore`**

`.gitignore`:
```
.env
__pycache__/
*.pyc
output/
.venv/
venv/
.pytest_cache/
```

- [ ] **Step 3: 写 `.env.example`**

`.env.example`:
```
ANTHROPIC_API_KEY=sk-ant-...
NOTION_TOKEN=ntn_...
NOTION_OVERVIEW_PARENT_PAGE_ID=
NOTION_OPINIONS_DATABASE_ID=
```

- [ ] **Step 4: 写 `requirements.txt`**

`requirements.txt`:
```
anthropic>=0.69
ebooklib>=0.18
beautifulsoup4>=4.12
pypdf>=5.1
notion-client>=2.2
python-dotenv>=1.0
pytest>=8.3
```

- [ ] **Step 5: 建包目录标记文件**

`engine/__init__.py`: （空文件）
```python
```

`tests/__init__.py`: （空文件）
```python
```

- [ ] **Step 6: 安装依赖**

Run:
```bash
cd "D:/workspace/investment" && pip install -r requirements.txt
```
Expected: `Successfully installed anthropic-... ebooklib-... ...`

- [ ] **Step 7: 提交**

```bash
cd "D:/workspace/investment" && git add .gitignore .env.example requirements.txt engine/__init__.py tests/__init__.py && git commit -m "chore: project scaffold and dependencies

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: 数据模型

**Files:**
- Create: `D:\workspace\investment\engine\models.py`
- Test: `D:\workspace\investment\tests\test_models.py`

- [ ] **Step 1: 写失败测试**

`tests/test_models.py`:
```python
from engine.models import Chapter, ChapterNote, OpinionEntry, BookSummary


def test_chapter_roundtrip():
    ch = Chapter(index=1, title="第一章", text="正文")
    assert ch.index == 1
    assert ch.title == "第一章"


def test_chapter_note_to_from_dict():
    note = ChapterNote(
        chapter_index=1,
        chapter_title="第一章",
        core_points=["观点A"],
        arguments=["论据A"],
        actionables=["要点A"],
        quotes=["金句A"],
        opinions=[
            OpinionEntry(
                opinion="永远不要满仓单一标的",
                chapter="第一章",
                tags=["风险控制", "仓位管理"],
                argument_summary="集中导致不可控回撤",
                actionability="原则",
                quote="不要把鸡蛋放在一个篮子里",
            )
        ],
        suggested_tags=[],
    )
    d = note.to_dict()
    restored = ChapterNote.from_dict(d)
    assert restored == note
    assert restored.opinions[0].tags == ["风险控制", "仓位管理"]


def test_book_summary_fields():
    s = BookSummary(
        book_title="聪明的投资者",
        author="格雷厄姆",
        one_liner="价值投资奠基之作",
        core_theses=["安全边际", "市场先生"],
        principles=["坚持安全边际"],
        open_questions=["如何估算内在价值需自己判断"],
    )
    assert s.author == "格雷厄姆"
    assert len(s.core_theses) == 2
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "D:/workspace/investment" && python -m pytest tests/test_models.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'engine.models'`

- [ ] **Step 3: 实现 `engine/models.py`**

`engine/models.py`:
```python
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List


@dataclass
class Chapter:
    index: int
    title: str
    text: str


@dataclass
class OpinionEntry:
    opinion: str                 # 观点（标题）
    chapter: str                 # 出处章节
    tags: List[str]              # 主题标签（取自固定表）
    argument_summary: str        # 论据摘要
    actionability: str           # 原则 / 可直接执行 / 需自己判断
    quote: str                   # 原文金句

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "OpinionEntry":
        return cls(**d)


@dataclass
class ChapterNote:
    chapter_index: int
    chapter_title: str
    core_points: List[str]
    arguments: List[str]
    actionables: List[str]
    quotes: List[str]
    opinions: List[OpinionEntry] = field(default_factory=list)
    suggested_tags: List[str] = field(default_factory=list)  # 建议新增标签

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ChapterNote":
        opinions = [OpinionEntry.from_dict(o) for o in d.get("opinions", [])]
        return cls(
            chapter_index=d["chapter_index"],
            chapter_title=d["chapter_title"],
            core_points=d["core_points"],
            arguments=d["arguments"],
            actionables=d["actionables"],
            quotes=d["quotes"],
            opinions=opinions,
            suggested_tags=d.get("suggested_tags", []),
        )


@dataclass
class BookSummary:
    book_title: str
    author: str
    one_liner: str
    core_theses: List[str]
    principles: List[str]
    open_questions: List[str]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "BookSummary":
        return cls(**d)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd "D:/workspace/investment" && python -m pytest tests/test_models.py -v`
Expected: PASS（3 个测试）

- [ ] **Step 5: 提交**

```bash
cd "D:/workspace/investment" && git add engine/models.py tests/test_models.py && git commit -m "feat: add core data models

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: 配置模块（固定标签表 + 常量）

**Files:**
- Create: `D:\workspace\investment\config.py`
- Test: `D:\workspace\investment\tests\test_config.py`

- [ ] **Step 1: 写失败测试**

`tests/test_config.py`:
```python
import config


def test_fixed_tags_present_and_unique():
    tags = config.FIXED_TAGS
    assert "风险控制" in tags
    assert "仓位管理" in tags
    assert len(tags) == len(set(tags)), "固定标签表不应有重复"


def test_model_and_thresholds():
    assert config.MODEL == "claude-opus-4-8"
    assert config.COST_ALERT_USD > 0
    assert config.HARD_SPLIT_CHARS > 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "D:/workspace/investment" && python -m pytest tests/test_config.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 3: 实现 `config.py`**

`config.py`:
```python
"""集中配置：固定标签表、模型、成本护栏、Notion ID。"""

# 精读用模型（质量优先）
MODEL = "claude-opus-4-8"

# 成本护栏：预估费用超过此值（美元）先请用户确认
COST_ALERT_USD = 10.0

# Opus 4.8 报价（美元 / 百万 token）
PRICE_INPUT_PER_M = 5.0
PRICE_OUTPUT_PER_M = 25.0

# 章节切分失败时的兜底：按字数硬切
HARD_SPLIT_CHARS = 8000

# 每章精读的输出上限（token）
MAX_TOKENS_PER_CHAPTER = 8000
# 合成总览的输出上限（token）
MAX_TOKENS_SYNTHESIS = 8000

# 固定主题标签表（用户可增删；AI 只能从中选取）
FIXED_TAGS = [
    "估值",
    "风险控制",
    "仓位管理",
    "市场心理",
    "择时",
    "财报分析",
    "资产配置",
    "安全边际",
    "复利",
    "分散化",
    "护城河/竞争优势",
    "宏观周期",
    "交易成本/税费",
    "投资纪律",
]

# 可执行度取值
ACTIONABILITY_VALUES = ["原则", "可直接执行", "需自己判断"]

# Notion 目标（从 .env 读取；此处仅占位说明，运行时由 read_book.py 注入）
# NOTION_OVERVIEW_PARENT_PAGE_ID / NOTION_OPINIONS_DATABASE_ID
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd "D:/workspace/investment" && python -m pytest tests/test_config.py -v`
Expected: PASS（2 个测试）

- [ ] **Step 5: 提交**

```bash
cd "D:/workspace/investment" && git add config.py tests/test_config.py && git commit -m "feat: add config with fixed tag table and cost guardrails

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: 解析器（TXT 优先，含硬切兜底）

**Files:**
- Create: `D:\workspace\investment\engine\parser.py`
- Create: `D:\workspace\investment\tests\fixtures\sample.txt`
- Test: `D:\workspace\investment\tests\test_parser.py`

- [ ] **Step 1: 建测试 fixture（小 TXT 书）**

`tests/fixtures/sample.txt`:
```
第一章 开端
这是第一章的正文内容，讲述投资的基本理念。
安全边际是核心。

第二章 进阶
这是第二章的正文，讲述风险控制。
永远不要满仓单一标的。

第三章 结语
这是第三章，总结全书。
坚持纪律。
```

- [ ] **Step 2: 写失败测试**

`tests/test_parser.py`:
```python
from engine.parser import parse_txt, hard_split, parse_book
from engine.models import Chapter


def test_parse_txt_splits_by_chapter_headers():
    chapters = parse_txt("tests/fixtures/sample.txt")
    assert len(chapters) == 3
    assert chapters[0].index == 1
    assert "第一章" in chapters[0].title
    assert "安全边际" in chapters[0].text
    assert chapters[1].index == 2
    assert "风险控制" in chapters[1].text


def test_hard_split_chunks_by_size():
    text = "字" * 25000
    chapters = hard_split(text, chunk_chars=8000)
    assert len(chapters) == 4  # 25000/8000 向上取整
    assert all(isinstance(c, Chapter) for c in chapters)
    assert chapters[0].index == 1
    assert "段" in chapters[0].title  # 硬切段标题含"段"


def test_parse_book_dispatches_on_extension():
    chapters = parse_book("tests/fixtures/sample.txt")
    assert len(chapters) == 3
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd "D:/workspace/investment" && python -m pytest tests/test_parser.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'engine.parser'`

- [ ] **Step 4: 实现 `engine/parser.py`**

`engine/parser.py`:
```python
from __future__ import annotations
import os
import re
import math
from typing import List
from engine.models import Chapter
import config

# 匹配中文章节标题行，如 "第一章 开端" / "第 12 章" / "第十章"
_CHAPTER_RE = re.compile(r"^\s*第\s*[0-9一二三四五六七八九十百零]+\s*章.*$")


def hard_split(text: str, chunk_chars: int = None) -> List[Chapter]:
    """章节识别失败时的兜底：按固定字数硬切。"""
    if chunk_chars is None:
        chunk_chars = config.HARD_SPLIT_CHARS
    text = text.strip()
    n = max(1, math.ceil(len(text) / chunk_chars))
    chapters: List[Chapter] = []
    for i in range(n):
        chunk = text[i * chunk_chars:(i + 1) * chunk_chars]
        chapters.append(Chapter(index=i + 1, title=f"第{i + 1}段", text=chunk))
    return chapters


def _split_by_headers(text: str) -> List[Chapter]:
    """按章节标题行切分；切不出（<2 章）则返回空列表交给硬切。"""
    lines = text.splitlines()
    header_idxs = [i for i, ln in enumerate(lines) if _CHAPTER_RE.match(ln)]
    if len(header_idxs) < 2:
        return []
    chapters: List[Chapter] = []
    for order, start in enumerate(header_idxs):
        end = header_idxs[order + 1] if order + 1 < len(header_idxs) else len(lines)
        title = lines[start].strip()
        body = "\n".join(lines[start + 1:end]).strip()
        chapters.append(Chapter(index=order + 1, title=title, text=body))
    return chapters


def parse_txt(path: str) -> List[Chapter]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    chapters = _split_by_headers(text)
    if not chapters:
        chapters = hard_split(text)
    return chapters


def parse_book(path: str) -> List[Chapter]:
    """按扩展名分派解析器。EPUB/PDF 在后续任务补齐。"""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".txt":
        return parse_txt(path)
    if ext == ".epub":
        from engine.parser_epub import parse_epub
        return parse_epub(path)
    if ext == ".pdf":
        from engine.parser_pdf import parse_pdf
        return parse_pdf(path)
    raise ValueError(f"不支持的文件类型：{ext}")
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd "D:/workspace/investment" && python -m pytest tests/test_parser.py -v`
Expected: PASS（3 个测试）

- [ ] **Step 6: 提交**

```bash
cd "D:/workspace/investment" && git add engine/parser.py tests/test_parser.py tests/fixtures/sample.txt && git commit -m "feat: add TXT parser with chapter detection and hard-split fallback

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: EPUB 解析器

**Files:**
- Create: `D:\workspace\investment\engine\parser_epub.py`
- Create: `D:\workspace\investment\tests\fixtures\make_sample_epub.py`
- Test: `D:\workspace\investment\tests\test_parser_epub.py`

- [ ] **Step 1: 建生成测试 EPUB 的脚本**

`tests/fixtures/make_sample_epub.py`:
```python
"""生成一个含 2 章的最小 EPUB，用于解析测试。运行一次即可。"""
from ebooklib import epub


def build(path: str):
    book = epub.EpubBook()
    book.set_identifier("id-sample")
    book.set_title("测试之书")
    book.add_author("测试作者")

    c1 = epub.EpubHtml(title="第一章", file_name="c1.xhtml", lang="zh")
    c1.content = "<h1>第一章 开端</h1><p>投资的基本理念，安全边际是核心。</p>"
    c2 = epub.EpubHtml(title="第二章", file_name="c2.xhtml", lang="zh")
    c2.content = "<h1>第二章 进阶</h1><p>风险控制，永远不要满仓单一标的。</p>"

    book.add_item(c1)
    book.add_item(c2)
    book.toc = (c1, c2)
    book.spine = ["nav", c1, c2]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    epub.write_epub(path, book)


if __name__ == "__main__":
    build("tests/fixtures/sample.epub")
    print("wrote tests/fixtures/sample.epub")
```

- [ ] **Step 2: 生成 fixture**

Run:
```bash
cd "D:/workspace/investment" && python tests/fixtures/make_sample_epub.py
```
Expected: `wrote tests/fixtures/sample.epub`

- [ ] **Step 3: 写失败测试**

`tests/test_parser_epub.py`:
```python
import os
import pytest
from engine.parser_epub import parse_epub

pytestmark = pytest.mark.skipif(
    not os.path.exists("tests/fixtures/sample.epub"),
    reason="先运行 tests/fixtures/make_sample_epub.py 生成 fixture",
)


def test_parse_epub_returns_chapters():
    chapters = parse_epub("tests/fixtures/sample.epub")
    assert len(chapters) >= 2
    joined = " ".join(c.text for c in chapters)
    assert "安全边际" in joined
    assert "风险控制" in joined
    # 标题应从 <h1> 或 spine 项提取，非空
    assert all(c.title.strip() for c in chapters)
    assert chapters[0].index == 1
```

- [ ] **Step 4: 运行测试确认失败**

Run: `cd "D:/workspace/investment" && python -m pytest tests/test_parser_epub.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'engine.parser_epub'`

- [ ] **Step 5: 实现 `engine/parser_epub.py`**

`engine/parser_epub.py`:
```python
from __future__ import annotations
from typing import List
from ebooklib import epub, ITEM_DOCUMENT
from bs4 import BeautifulSoup
from engine.models import Chapter
from engine.parser import hard_split


def _html_to_title_text(html: str, fallback_title: str):
    soup = BeautifulSoup(html, "html.parser")
    h = soup.find(["h1", "h2", "title"])
    title = h.get_text(strip=True) if h and h.get_text(strip=True) else fallback_title
    text = soup.get_text("\n", strip=True)
    return title, text


def parse_epub(path: str) -> List[Chapter]:
    book = epub.read_epub(path)
    chapters: List[Chapter] = []
    order = 0
    for item in book.get_items_of_type(ITEM_DOCUMENT):
        html = item.get_content().decode("utf-8", errors="ignore")
        title, text = _html_to_title_text(html, fallback_title=item.get_name())
        if not text.strip():
            continue
        order += 1
        chapters.append(Chapter(index=order, title=title, text=text))

    # 兜底：若只解析出 1 个巨大文档，按字数硬切
    if len(chapters) == 1:
        chapters = hard_split(chapters[0].text)
    return chapters
```

- [ ] **Step 6: 运行测试确认通过**

Run: `cd "D:/workspace/investment" && python -m pytest tests/test_parser_epub.py -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
cd "D:/workspace/investment" && git add engine/parser_epub.py tests/test_parser_epub.py tests/fixtures/make_sample_epub.py tests/fixtures/sample.epub && git commit -m "feat: add EPUB parser

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: PDF 解析器

**Files:**
- Create: `D:\workspace\investment\engine\parser_pdf.py`
- Test: `D:\workspace\investment\tests\test_parser_pdf.py`

- [ ] **Step 1: 写失败测试（生成临时 PDF 再解析）**

`tests/test_parser_pdf.py`:
```python
import pytest
from engine.parser_pdf import parse_pdf


def _make_pdf(path):
    # 用 pypdf 无法直接写文字页；改用 reportlab 若可用，否则跳过
    reportlab = pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(path)
    c.drawString(72, 800, "第一章 开端")
    c.drawString(72, 780, "安全边际是核心")
    c.showPage()
    c.drawString(72, 800, "第二章 进阶")
    c.drawString(72, 780, "风险控制很重要")
    c.showPage()
    c.save()


def test_parse_pdf_extracts_text(tmp_path):
    p = tmp_path / "sample.pdf"
    _make_pdf(str(p))
    chapters = parse_pdf(str(p))
    joined = " ".join(c.text for c in chapters)
    assert "安全边际" in joined
    assert chapters[0].index == 1
```

- [ ] **Step 2: 安装 reportlab（仅测试用）并运行确认失败**

Run:
```bash
cd "D:/workspace/investment" && pip install reportlab && python -m pytest tests/test_parser_pdf.py -v
```
Expected: FAIL —— `ModuleNotFoundError: No module named 'engine.parser_pdf'`

- [ ] **Step 3: 实现 `engine/parser_pdf.py`**

`engine/parser_pdf.py`:
```python
from __future__ import annotations
from typing import List
from pypdf import PdfReader
from engine.models import Chapter
from engine.parser import _split_by_headers, hard_split


def parse_pdf(path: str) -> List[Chapter]:
    reader = PdfReader(path)
    full_text = "\n".join((page.extract_text() or "") for page in reader.pages)

    # 先尝试按章节标题切；失败则按字数硬切
    chapters = _split_by_headers(full_text)
    if not chapters:
        chapters = hard_split(full_text)
    return chapters
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd "D:/workspace/investment" && python -m pytest tests/test_parser_pdf.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd "D:/workspace/investment" && git add engine/parser_pdf.py tests/test_parser_pdf.py && git commit -m "feat: add PDF parser with header split and hard-split fallback

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: 成本估算与护栏

**Files:**
- Create: `D:\workspace\investment\engine\cost.py`
- Test: `D:\workspace\investment\tests\test_cost.py`

- [ ] **Step 1: 写失败测试**

`tests/test_cost.py`:
```python
from engine.cost import estimate_input_tokens, estimate_cost_usd
from engine.models import Chapter


def test_estimate_input_tokens_scales_with_length():
    chapters = [Chapter(index=1, title="t", text="字" * 10000)]
    tokens = estimate_input_tokens(chapters)
    # 中文约 1 字 ≈ 1.5 token，10000 字 ≈ 15000，允许合理区间
    assert 12000 <= tokens <= 20000


def test_estimate_cost_usd_uses_prices():
    # 40万 input + 7万 output（Opus: $5/$25 每百万）≈ 2 + 1.75 = 3.75
    cost = estimate_cost_usd(input_tokens=400_000, output_tokens=70_000)
    assert 3.5 <= cost <= 4.0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "D:/workspace/investment" && python -m pytest tests/test_cost.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'engine.cost'`

- [ ] **Step 3: 实现 `engine/cost.py`**

`engine/cost.py`:
```python
from __future__ import annotations
from typing import List
from engine.models import Chapter
import config

# 中文近似：1 字 ≈ 1.5 token
_CHARS_TO_TOKENS = 1.5
# 输出经验值：每章输出 token 占该章输入的比例（用于全书估算）
_OUTPUT_RATIO = 0.18


def estimate_input_tokens(chapters: List[Chapter]) -> int:
    chars = sum(len(c.text) for c in chapters)
    return int(chars * _CHARS_TO_TOKENS)


def estimate_output_tokens(input_tokens: int) -> int:
    return int(input_tokens * _OUTPUT_RATIO)


def estimate_cost_usd(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens / 1_000_000 * config.PRICE_INPUT_PER_M
        + output_tokens / 1_000_000 * config.PRICE_OUTPUT_PER_M
    )


def preflight(chapters: List[Chapter]) -> dict:
    """返回估算结果，供 CLI 展示与护栏判断。"""
    in_tok = estimate_input_tokens(chapters)
    out_tok = estimate_output_tokens(in_tok)
    cost = estimate_cost_usd(in_tok, out_tok)
    return {
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "cost_usd": round(cost, 2),
        "over_threshold": cost > config.COST_ALERT_USD,
    }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd "D:/workspace/investment" && python -m pytest tests/test_cost.py -v`
Expected: PASS（2 个测试）

- [ ] **Step 5: 提交**

```bash
cd "D:/workspace/investment" && git add engine/cost.py tests/test_cost.py && git commit -m "feat: add cost estimation and preflight guardrail

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: 缓存与 Markdown 备份

**Files:**
- Create: `D:\workspace\investment\engine\cache.py`
- Test: `D:\workspace\investment\tests\test_cache.py`

- [ ] **Step 1: 写失败测试**

`tests/test_cache.py`:
```python
from engine.cache import (
    save_chapter_note, load_chapter_note, has_chapter_note, write_markdown,
)
from engine.models import ChapterNote, OpinionEntry, BookSummary


def _note():
    return ChapterNote(
        chapter_index=3,
        chapter_title="第三章",
        core_points=["观点"],
        arguments=["论据"],
        actionables=["要点"],
        quotes=["金句"],
        opinions=[OpinionEntry(
            opinion="坚持纪律", chapter="第三章", tags=["投资纪律"],
            argument_summary="纪律带来一致性", actionability="原则", quote="纪律即自由",
        )],
        suggested_tags=[],
    )


def test_chapter_note_cache_roundtrip(tmp_path):
    book = "测试之书"
    note = _note()
    assert not has_chapter_note(book, 3, base=str(tmp_path))
    save_chapter_note(book, note, base=str(tmp_path))
    assert has_chapter_note(book, 3, base=str(tmp_path))
    loaded = load_chapter_note(book, 3, base=str(tmp_path))
    assert loaded == note


def test_write_markdown_creates_file(tmp_path):
    book = "测试之书"
    summary = BookSummary(
        book_title=book, author="作者", one_liner="一句话",
        core_theses=["核心1"], principles=["原则1"], open_questions=["疑问1"],
    )
    path = write_markdown(book, summary, [_note()], base=str(tmp_path))
    content = open(path, encoding="utf-8").read()
    assert "测试之书" in content
    assert "核心1" in content
    assert "坚持纪律" in content
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "D:/workspace/investment" && python -m pytest tests/test_cache.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'engine.cache'`

- [ ] **Step 3: 实现 `engine/cache.py`**

`engine/cache.py`:
```python
from __future__ import annotations
import os
import json
import re
from typing import List, Optional
from engine.models import ChapterNote, BookSummary

_DEFAULT_BASE = "output"


def _safe(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()


def _cache_dir(book: str, base: str) -> str:
    return os.path.join(base, ".cache", _safe(book))


def _note_path(book: str, index: int, base: str) -> str:
    return os.path.join(_cache_dir(book, base), f"第{index}章.json")


def has_chapter_note(book: str, index: int, base: str = _DEFAULT_BASE) -> bool:
    return os.path.exists(_note_path(book, index, base))


def save_chapter_note(book: str, note: ChapterNote, base: str = _DEFAULT_BASE) -> None:
    d = _cache_dir(book, base)
    os.makedirs(d, exist_ok=True)
    with open(_note_path(book, note.chapter_index, base), "w", encoding="utf-8") as f:
        json.dump(note.to_dict(), f, ensure_ascii=False, indent=2)


def load_chapter_note(book: str, index: int, base: str = _DEFAULT_BASE) -> Optional[ChapterNote]:
    p = _note_path(book, index, base)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return ChapterNote.from_dict(json.load(f))


def write_markdown(book: str, summary: BookSummary, notes: List[ChapterNote],
                   base: str = _DEFAULT_BASE) -> str:
    os.makedirs(base, exist_ok=True)
    path = os.path.join(base, f"{_safe(book)}.md")
    lines: List[str] = []
    lines.append(f"# 📖 {summary.book_title}（{summary.author}）\n")
    lines.append(f"**一句话总结：** {summary.one_liner}\n")
    lines.append("## 全书核心论点")
    lines += [f"- {t}" for t in summary.core_theses]
    lines.append("\n## 提炼的投资原则 / 可执行清单")
    lines += [f"- {p}" for p in summary.principles]
    lines.append("\n## 逐章笔记")
    for note in sorted(notes, key=lambda n: n.chapter_index):
        lines.append(f"\n### {note.chapter_title}")
        lines.append("**核心观点：**")
        lines += [f"- {x}" for x in note.core_points]
        lines.append("**论据：**")
        lines += [f"- {x}" for x in note.arguments]
        lines.append("**可执行要点：**")
        lines += [f"- {x}" for x in note.actionables]
        lines.append("**金句：**")
        lines += [f"> {x}" for x in note.quotes]
    lines.append("\n## 我的疑问 & 待验证点")
    lines += [f"- {q}" for q in summary.open_questions]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd "D:/workspace/investment" && python -m pytest tests/test_cache.py -v`
Expected: PASS（2 个测试）

- [ ] **Step 5: 提交**

```bash
cd "D:/workspace/investment" && git add engine/cache.py tests/test_cache.py && git commit -m "feat: add local cache and markdown backup

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 9: 精读器（调用 Opus 4.8，结构化输出）

**Files:**
- Create: `D:\workspace\investment\engine\reader.py`

**说明：** 精读器真实调用 Opus，不写自动化单测（避免烧钱、质量需人眼验收）。本任务通过一次真实单章调用手工验证（Step 3）。需要 `.env` 中已有 `ANTHROPIC_API_KEY`。

- [ ] **Step 1: 实现 `engine/reader.py`**

`engine/reader.py`:
```python
from __future__ import annotations
import json
from anthropic import Anthropic
from engine.models import Chapter, ChapterNote, OpinionEntry
import config

_client = Anthropic()  # 从环境变量 ANTHROPIC_API_KEY 读取

# 每章笔记的 JSON schema（结构化输出，保证干净 JSON）
_CHAPTER_SCHEMA = {
    "type": "object",
    "properties": {
        "core_points": {"type": "array", "items": {"type": "string"}},
        "arguments": {"type": "array", "items": {"type": "string"}},
        "actionables": {"type": "array", "items": {"type": "string"}},
        "quotes": {"type": "array", "items": {"type": "string"}},
        "opinions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "opinion": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "argument_summary": {"type": "string"},
                    "actionability": {"type": "string", "enum": config.ACTIONABILITY_VALUES},
                    "quote": {"type": "string"},
                },
                "required": ["opinion", "tags", "argument_summary", "actionability", "quote"],
                "additionalProperties": False,
            },
        },
        "suggested_tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["core_points", "arguments", "actionables", "quotes", "opinions", "suggested_tags"],
    "additionalProperties": False,
}


def _build_prompt(chapter: Chapter) -> str:
    tag_list = "、".join(config.FIXED_TAGS)
    return f"""你是一位严谨的投资书籍精读助手。请精读下面这一章，提炼结构化笔记。

要求：
- 忠于原文，不臆造。金句必须是原文引用。
- opinions（核心观点）中每条的 tags 只能从这个固定标签表中选：{tag_list}
- 若某观点确实无法归入上述标签，在 suggested_tags 中写"建议新增：XXX"，但 tags 字段仍从固定表里选最接近的。
- actionability 只能是：{"、".join(config.ACTIONABILITY_VALUES)}
- 对于书中需要读者自行判断、不能照搬的地方，在 opinions 里用 actionability="需自己判断" 标出。

章节标题：{chapter.title}

章节正文：
{chapter.text}
"""


def read_chapter(chapter: Chapter) -> ChapterNote:
    resp = _client.messages.create(
        model=config.MODEL,
        max_tokens=config.MAX_TOKENS_PER_CHAPTER,
        thinking={"type": "adaptive"},
        output_config={"format": {"type": "json_schema", "schema": _CHAPTER_SCHEMA}},
        messages=[{"role": "user", "content": _build_prompt(chapter)}],
    )
    text = next(b.text for b in resp.content if b.type == "text")
    data = json.loads(text)

    opinions = [
        OpinionEntry(
            opinion=o["opinion"],
            chapter=chapter.title,
            tags=o["tags"],
            argument_summary=o["argument_summary"],
            actionability=o["actionability"],
            quote=o["quote"],
        )
        for o in data["opinions"]
    ]
    return ChapterNote(
        chapter_index=chapter.index,
        chapter_title=chapter.title,
        core_points=data["core_points"],
        arguments=data["arguments"],
        actionables=data["actionables"],
        quotes=data["quotes"],
        opinions=opinions,
        suggested_tags=data.get("suggested_tags", []),
    )
```

- [ ] **Step 2: 提示用户填好 `.env`**

确认 `D:\workspace\investment\.env` 存在且含 `ANTHROPIC_API_KEY`（从 `.env.example` 复制填入）。若无，暂停并请用户提供 key。

- [ ] **Step 3: 用单章短文本手工验证**

Run（临时脚本，验证后删除）:
```bash
cd "D:/workspace/investment" && python -c "from dotenv import load_dotenv; load_dotenv(); from engine.parser import parse_txt; from engine.reader import read_chapter; ch=parse_txt('tests/fixtures/sample.txt')[1]; note=read_chapter(ch); print('章节:',note.chapter_title); print('核心观点:',note.core_points); print('观点条目数:',len(note.opinions)); print('第一条tags:',note.opinions[0].tags if note.opinions else None)"
```
Expected: 打印出该章的核心观点、观点条目，且 tags 全部落在固定标签表内。人工确认笔记忠于原文、tags 合理。

- [ ] **Step 4: 提交**

```bash
cd "D:/workspace/investment" && git add engine/reader.py && git commit -m "feat: add chapter reader using Opus 4.8 structured output

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 10: 合成器（全书总览 + 观点条目汇总）

**Files:**
- Create: `D:\workspace\investment\engine\synthesizer.py`

**说明：** 合成器同样真实调用 Opus，通过手工验证（不写自动化单测）。

- [ ] **Step 1: 实现 `engine/synthesizer.py`**

`engine/synthesizer.py`:
```python
from __future__ import annotations
import json
from typing import List, Tuple
from anthropic import Anthropic
from engine.models import ChapterNote, BookSummary, OpinionEntry
import config

_client = Anthropic()

_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "one_liner": {"type": "string"},
        "core_theses": {"type": "array", "items": {"type": "string"}},
        "principles": {"type": "array", "items": {"type": "string"}},
        "open_questions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["one_liner", "core_theses", "principles", "open_questions"],
    "additionalProperties": False,
}


def _digest(notes: List[ChapterNote]) -> str:
    parts = []
    for n in sorted(notes, key=lambda x: x.chapter_index):
        parts.append(f"【{n.chapter_title}】")
        parts.append("核心观点：" + "；".join(n.core_points))
        parts.append("可执行要点：" + "；".join(n.actionables))
    return "\n".join(parts)


def synthesize(book_title: str, author: str,
               notes: List[ChapterNote]) -> Tuple[BookSummary, List[OpinionEntry]]:
    prompt = f"""下面是《{book_title}》（作者：{author}）各章的精读笔记摘要。
请据此产出全书层面的总结，帮助读者建立投资体系。

要求：
- one_liner：一句话总结全书。
- core_theses：全书 3-5 条核心论点。
- principles：提炼成可执行的投资原则/清单（读者能照着做的）。
- open_questions：书中需要读者自己判断、不能照搬的关键点。

各章摘要：
{_digest(notes)}
"""
    resp = _client.messages.create(
        model=config.MODEL,
        max_tokens=config.MAX_TOKENS_SYNTHESIS,
        thinking={"type": "adaptive"},
        output_config={"format": {"type": "json_schema", "schema": _SUMMARY_SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    )
    text = next(b.text for b in resp.content if b.type == "text")
    data = json.loads(text)

    summary = BookSummary(
        book_title=book_title,
        author=author,
        one_liner=data["one_liner"],
        core_theses=data["core_theses"],
        principles=data["principles"],
        open_questions=data["open_questions"],
    )

    # 观点条目直接汇总各章 opinions（合成阶段不重新调模型，忠于逐章产出）
    opinions: List[OpinionEntry] = []
    for n in sorted(notes, key=lambda x: x.chapter_index):
        opinions.extend(n.opinions)

    return summary, opinions
```

- [ ] **Step 2: 手工验证（用 fixture 两章跑通）**

Run（临时验证，需 `.env`）:
```bash
cd "D:/workspace/investment" && python -c "from dotenv import load_dotenv; load_dotenv(); from engine.parser import parse_txt; from engine.reader import read_chapter; from engine.synthesizer import synthesize; chs=parse_txt('tests/fixtures/sample.txt'); notes=[read_chapter(c) for c in chs]; s,ops=synthesize('测试之书','测试作者',notes); print('一句话:',s.one_liner); print('核心论点:',s.core_theses); print('原则:',s.principles); print('观点条目:',len(ops))"
```
Expected: 打印出全书一句话总结、核心论点、投资原则、汇总的观点条目数。人工确认合理。

- [ ] **Step 3: 提交**

```bash
cd "D:/workspace/investment" && git add engine/synthesizer.py && git commit -m "feat: add synthesizer for book-level summary and principles

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 11: Notion 写入器（mock 单测）

**Files:**
- Create: `D:\workspace\investment\engine\notion_writer.py`
- Test: `D:\workspace\investment\tests\test_notion_writer.py`

**说明：** 用 mock 的 Notion client 验证字段映射正确，不触真实 API。

- [ ] **Step 1: 写失败测试（mock client）**

`tests/test_notion_writer.py`:
```python
from unittest.mock import MagicMock
from engine.notion_writer import write_opinion_rows, build_opinion_properties
from engine.models import OpinionEntry


def _op():
    return OpinionEntry(
        opinion="永远不要满仓单一标的",
        chapter="第二章",
        tags=["风险控制", "仓位管理"],
        argument_summary="集中导致不可控回撤",
        actionability="原则",
        quote="不要把鸡蛋放在一个篮子里",
    )


def test_build_opinion_properties_maps_all_fields():
    props = build_opinion_properties(_op(), book_title="聪明的投资者")
    assert props["观点"]["title"][0]["text"]["content"] == "永远不要满仓单一标的"
    assert props["来源书"]["rich_text"][0]["text"]["content"] == "聪明的投资者"
    assert props["章节"]["rich_text"][0]["text"]["content"] == "第二章"
    tag_names = [t["name"] for t in props["主题标签"]["multi_select"]]
    assert "风险控制" in tag_names and "仓位管理" in tag_names
    assert props["可执行度"]["select"]["name"] == "原则"
    assert props["原文金句"]["rich_text"][0]["text"]["content"].startswith("不要把")


def test_write_opinion_rows_calls_create_per_opinion():
    client = MagicMock()
    write_opinion_rows(client, database_id="db123",
                       opinions=[_op(), _op()], book_title="聪明的投资者")
    assert client.pages.create.call_count == 2
    _, kwargs = client.pages.create.call_args
    assert kwargs["parent"] == {"database_id": "db123"}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "D:/workspace/investment" && python -m pytest tests/test_notion_writer.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'engine.notion_writer'`

- [ ] **Step 3: 实现 `engine/notion_writer.py`**

`engine/notion_writer.py`:
```python
from __future__ import annotations
from typing import List
from engine.models import OpinionEntry, BookSummary, ChapterNote


def _rt(text: str) -> dict:
    return {"rich_text": [{"text": {"content": text[:2000]}}]}


def _title(text: str) -> dict:
    return {"title": [{"text": {"content": text[:2000]}}]}


def build_opinion_properties(op: OpinionEntry, book_title: str) -> dict:
    return {
        "观点": _title(op.opinion),
        "来源书": _rt(book_title),
        "章节": _rt(op.chapter),
        "主题标签": {"multi_select": [{"name": t} for t in op.tags]},
        "论据摘要": _rt(op.argument_summary),
        "可执行度": {"select": {"name": op.actionability}},
        "原文金句": _rt(op.quote),
    }


def write_opinion_rows(client, database_id: str,
                       opinions: List[OpinionEntry], book_title: str) -> int:
    count = 0
    for op in opinions:
        client.pages.create(
            parent={"database_id": database_id},
            properties=build_opinion_properties(op, book_title),
        )
        count += 1
    return count


def _para(text: str) -> dict:
    return {"object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{"text": {"content": text[:2000]}}]}}


def _heading(text: str) -> dict:
    return {"object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [{"text": {"content": text[:2000]}}]}}


def _bullet(text: str) -> dict:
    return {"object": "block", "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [{"text": {"content": text[:2000]}}]}}


def build_overview_blocks(summary: BookSummary, notes: List[ChapterNote]) -> List[dict]:
    blocks: List[dict] = []
    blocks.append(_para(f"一句话总结：{summary.one_liner}"))
    blocks.append(_heading("全书核心论点"))
    blocks += [_bullet(t) for t in summary.core_theses]
    blocks.append(_heading("提炼的投资原则 / 可执行清单"))
    blocks += [_bullet(p) for p in summary.principles]
    blocks.append(_heading("逐章笔记"))
    for n in sorted(notes, key=lambda x: x.chapter_index):
        blocks.append(_heading(n.chapter_title))
        for x in n.core_points:
            blocks.append(_bullet(f"核心：{x}"))
        for x in n.actionables:
            blocks.append(_bullet(f"可执行：{x}"))
        for x in n.quotes:
            blocks.append(_bullet(f"金句：{x}"))
    blocks.append(_heading("我的疑问 & 待验证点"))
    blocks += [_bullet(q) for q in summary.open_questions]
    return blocks


def write_overview_page(client, parent_page_id: str,
                        summary: BookSummary, notes: List[ChapterNote]) -> str:
    # Notion 单次 children 上限 100，分批追加
    blocks = build_overview_blocks(summary, notes)
    page = client.pages.create(
        parent={"page_id": parent_page_id},
        properties={"title": [{"text": {"content":
                    f"📖 {summary.book_title}（{summary.author}）"}}]},
        children=blocks[:100],
    )
    page_id = page["id"]
    for i in range(100, len(blocks), 100):
        client.blocks.children.append(block_id=page_id, children=blocks[i:i + 100])
    return page_id
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd "D:/workspace/investment" && python -m pytest tests/test_notion_writer.py -v`
Expected: PASS（2 个测试）

- [ ] **Step 5: 提交**

```bash
cd "D:/workspace/investment" && git add engine/notion_writer.py tests/test_notion_writer.py && git commit -m "feat: add notion writer for overview page and opinion database

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 12: 主编排 CLI（read_book.py）+ 独立 Notion 重跑（push_to_notion.py）

**Files:**
- Create: `D:\workspace\investment\read_book.py`
- Create: `D:\workspace\investment\push_to_notion.py`

**说明：** 编排全流程；断点续跑靠 cache；Notion 写入可用 `push_to_notion.py` 单独重跑。真实端到端由 Step 3 验证。

- [ ] **Step 1: 实现 `read_book.py`**

`read_book.py`:
```python
from __future__ import annotations
import os
import sys
import argparse
from dotenv import load_dotenv
from notion_client import Client as NotionClient

from engine.parser import parse_book
from engine.reader import read_chapter
from engine.synthesizer import synthesize
from engine.cache import (
    has_chapter_note, save_chapter_note, load_chapter_note, write_markdown,
)
from engine.notion_writer import write_overview_page, write_opinion_rows
from engine.cost import preflight
import config

load_dotenv()


def book_name_from_path(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def run(path: str, author: str, skip_notion: bool = False, yes: bool = False):
    book = book_name_from_path(path)

    print(f"[1/4] 解析…… {path}")
    chapters = parse_book(path)
    print(f"      识别出 {len(chapters)} 章，共 {sum(len(c.text) for c in chapters)} 字")

    est = preflight(chapters)
    print(f"      预估：输入~{est['input_tokens']} tok，输出~{est['output_tokens']} tok，"
          f"约 ${est['cost_usd']}")
    if est["over_threshold"] and not yes:
        ans = input(f"预估花费超过 ${config.COST_ALERT_USD}，继续？(y/N) ").strip().lower()
        if ans != "y":
            print("已取消。")
            return

    print(f"[2/4] 逐章精读…… ({config.MODEL})")
    notes = []
    for ch in chapters:
        if has_chapter_note(book, ch.index):
            print(f"      第 {ch.index}/{len(chapters)} 章 (缓存命中) ✓")
            notes.append(load_chapter_note(book, ch.index))
            continue
        note = read_chapter(ch)
        save_chapter_note(book, note)       # 边读边落地，支持断点续跑
        notes.append(note)
        print(f"      第 {ch.index}/{len(chapters)} 章 ✓")

    print("[3/4] 合成全书总览 & 提炼投资原则……")
    summary, opinions = synthesize(book, author, notes)

    md_path = write_markdown(book, summary, notes)
    print(f"      本地备份 → {md_path}")

    if skip_notion:
        print("[4/4] 跳过 Notion（--skip-notion）。稍后可运行 push_to_notion.py")
        return

    print("[4/4] 写入 Notion……")
    _push(book, author, summary, notes, opinions)


def _push(book, author, summary, notes, opinions):
    token = os.environ["NOTION_TOKEN"]
    parent_page = os.environ["NOTION_OVERVIEW_PARENT_PAGE_ID"]
    db_id = os.environ["NOTION_OPINIONS_DATABASE_ID"]
    client = NotionClient(auth=token)
    page_id = write_overview_page(client, parent_page, summary, notes)
    print(f"      总览页面 ✓ ({page_id})")
    n = write_opinion_rows(client, db_id, opinions, book)
    print(f"      观点数据库 +{n} 条 ✓")


def main():
    ap = argparse.ArgumentParser(description="AI 精读投资书籍 → Notion")
    ap.add_argument("path", help="电子书路径 (.epub/.pdf/.txt)")
    ap.add_argument("--author", default="未知", help="作者名")
    ap.add_argument("--skip-notion", action="store_true", help="只精读+本地备份，不写 Notion")
    ap.add_argument("--yes", action="store_true", help="跳过成本确认")
    args = ap.parse_args()
    if not os.path.exists(args.path):
        print(f"文件不存在：{args.path}"); sys.exit(1)
    run(args.path, args.author, args.skip_notion, args.yes)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 实现 `push_to_notion.py`**

`push_to_notion.py`:
```python
from __future__ import annotations
import os
import sys
import argparse
from dotenv import load_dotenv
from notion_client import Client as NotionClient

from engine.cache import load_chapter_note, _cache_dir  # 复用缓存
from engine.synthesizer import synthesize
from engine.notion_writer import write_overview_page, write_opinion_rows

load_dotenv()


def _load_all_notes(book: str):
    d = _cache_dir(book, "output")
    if not os.path.isdir(d):
        print(f"没有找到缓存：{d}，请先运行 read_book.py"); sys.exit(1)
    notes = []
    idx = 1
    while True:
        note = load_chapter_note(book, idx)
        if note is None:
            break
        notes.append(note); idx += 1
    if not notes:
        print("缓存为空。"); sys.exit(1)
    return notes


def main():
    ap = argparse.ArgumentParser(description="从本地缓存单独重跑 Notion 写入")
    ap.add_argument("book", help="书名（output/.cache 下的目录名）")
    ap.add_argument("--author", default="未知")
    args = ap.parse_args()

    notes = _load_all_notes(args.book)
    summary, opinions = synthesize(args.book, args.author, notes)

    client = NotionClient(auth=os.environ["NOTION_TOKEN"])
    page_id = write_overview_page(
        client, os.environ["NOTION_OVERVIEW_PARENT_PAGE_ID"], summary, notes)
    print(f"总览页面 ✓ ({page_id})")
    n = write_opinion_rows(
        client, os.environ["NOTION_OPINIONS_DATABASE_ID"], opinions, args.book)
    print(f"观点数据库 +{n} 条 ✓")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 端到端验证（先本地、后 Notion）**

先只跑本地（不碰 Notion，验证断点续跑与备份）:
```bash
cd "D:/workspace/investment" && python read_book.py tests/fixtures/sample.txt --author "测试作者" --skip-notion --yes
```
Expected: 打印 4 步进度（Notion 跳过），生成 `output/测试之书.md` 与 `output/.cache/测试之书/第N章.json`。再运行一次同命令，应看到"缓存命中"，不重复调 API。

Notion 授权就绪后（用户已建好数据库并填入 `.env`），跑真实一本熟悉的书验收:
```bash
cd "D:/workspace/investment" && python read_book.py "books/你选的书.epub" --author "作者名"
```
Expected: 总览页面与观点条目出现在 Notion；人工对照原书检查忠实度、tags 合理性、"需自己判断"标记到位。

- [ ] **Step 4: 提交**

```bash
cd "D:/workspace/investment" && git add read_book.py push_to_notion.py && git commit -m "feat: add CLI orchestration with resume and standalone notion push

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 13: 使用说明 README

**Files:**
- Create: `D:\workspace\investment\README.md`

- [ ] **Step 1: 写 `README.md`**

`README.md`:
```markdown
# AI 精读投资书籍 → Notion 笔记引擎

把电子书逐章喂给 Claude Opus 4.8 精读，产出结构化笔记，写入 Notion（总览页面 + 可跨书检索的观点数据库），并在本地留 Markdown 备份。

## 安装
1. 安装依赖：`pip install -r requirements.txt`
2. 复制 `.env.example` 为 `.env`，填入：
   - `ANTHROPIC_API_KEY`
   - `NOTION_TOKEN`（Notion 集成 token）
   - `NOTION_OVERVIEW_PARENT_PAGE_ID`（总览页面的父页面 ID，并把该页面共享给集成）
   - `NOTION_OPINIONS_DATABASE_ID`（观点数据库 ID，字段见下，并共享给集成）

## Notion 数据库字段（需手动建一次）
| 字段 | 类型 |
|---|---|
| 观点 | 标题 (Title) |
| 来源书 | 文本 (Text) |
| 章节 | 文本 (Text) |
| 主题标签 | 多选 (Multi-select) |
| 论据摘要 | 文本 (Text) |
| 可执行度 | 选择 (Select) |
| 原文金句 | 文本 (Text) |

## 使用
```bash
python read_book.py "books/某本书.epub" --author "作者名"
```
选项：
- `--skip-notion`：只精读 + 本地备份，不写 Notion
- `--yes`：跳过成本确认
- 中断后重跑同一命令会自动跳过已完成章节（断点续跑）

只重跑 Notion 写入（读本地缓存）：
```bash
python push_to_notion.py "书名" --author "作者名"
```

## 自定义标签
编辑 `config.py` 的 `FIXED_TAGS`。AI 只会从这个固定表里选主题标签。

## 测试
```bash
python -m pytest -v
```
```

- [ ] **Step 2: 提交**

```bash
cd "D:/workspace/investment" && git add README.md && git commit -m "docs: add README with setup and usage

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 14: 全量测试与收尾

- [ ] **Step 1: 运行全部离线测试**

Run: `cd "D:/workspace/investment" && python -m pytest -v`
Expected: 全部 PASS（models / config / parser / parser_epub / parser_pdf / cost / cache / notion_writer）。

- [ ] **Step 2: 确认精读器/合成器已人工验收**

确认 Task 9 Step 3、Task 10 Step 2、Task 12 Step 3 的手工验证均已通过、笔记质量满意。

- [ ] **Step 3: 最终提交（若有未提交变更）**

```bash
cd "D:/workspace/investment" && git add -A && git commit -m "chore: finalize reading engine v1" || echo "nothing to commit"
```

---

## 自我复核（对照 spec）

**1. Spec 覆盖检查**
- 四模块架构（解析/精读/合成/Notion 写入）→ Task 4-6 / 9 / 10 / 11 ✓
- 数据结构：总览页面 + 观点数据库字段 → Task 2（models）、Task 8（markdown）、Task 11（notion 映射）✓
- 固定标签表 → Task 3（config.FIXED_TAGS）+ Task 9（prompt 约束）✓
- 分章精读 + 结构化 JSON → Task 9（output_config.format）✓
- 合成总览 + 投资原则 + 疑问/待验证 → Task 10 ✓
- 断点续跑（每章缓存）→ Task 8 + Task 12 ✓
- 章节切分失败硬切兜底 → Task 4 hard_split，Task 5/6 调用 ✓
- API 限流重试 → anthropic SDK 默认重试（Task 9/10 说明）✓
- Notion 写入可单独重跑 → Task 12 push_to_notion.py ✓
- 成本护栏 → Task 7 + Task 12 preflight/确认 ✓
- 本地 Markdown 备份 → Task 8 write_markdown ✓
- 技术选型（Python/anthropic/ebooklib/pypdf/notion-client/dotenv）→ Task 1 requirements ✓
- 测试策略（解析/写入器离线单测；精读/合成人工验收；先一本再扩展）→ Task 4-8/11 单测 + Task 9/10/12 人工验收 ✓
- 用户准备（API key / Notion token / Python 库）→ Task 1 + Task 13 README ✓

无遗漏。

**2. 占位符扫描**：无 TBD/TODO；每个代码步骤含完整代码；命令含预期输出。✓

**3. 类型一致性**：`Chapter/ChapterNote/OpinionEntry/BookSummary` 字段在 models（Task 2）定义，reader/synthesizer/cache/notion_writer 全部按此字段名使用；`FIXED_TAGS/ACTIONABILITY_VALUES/MODEL` 在 config（Task 3）定义并被 reader/synthesizer 引用；`hard_split/_split_by_headers` 在 parser（Task 4）定义并被 parser_epub/parser_pdf 复用；`_cache_dir/load_chapter_note` 在 cache（Task 8）定义并被 push_to_notion 复用。命名一致。✓
