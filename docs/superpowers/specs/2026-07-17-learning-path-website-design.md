# 设计文档：投资理论知识学习路径网站（子项目 B）

- 日期：2026-07-17
- 状态：已写完并完成自检，待用户复核
- 作者：与用户协作 brainstorm 产出
- 前置：`docs/superpowers/specs/2026-07-16-ai-reading-investment-books-design.md`（子项目 A）

## 背景与目标

子项目 A 已把电子书精读为结构化笔记（本地 `output/.cache` + Markdown，以及 Notion 总览页/观点库）。用户需要一个**本地网站**，把这些素材重组为**主题 + 难度**的学习路径，用来系统学习投资**理论知识**（不是模拟交易或实盘工具）。

本 spec 覆盖愿景中的 **B) 个性化学习课程网站**。子项目 C（对话导师）另行设计，可复用同一素材与本站的 lesson 标识。

### 需求确认（来自 brainstorm）

| 维度 | 用户选择 |
|---|---|
| 交付形态 | 本地 FastAPI 网站（方案 2：构建与浏览合一） |
| 学习目的 | 吃透笔记中的理论知识 |
| 路径组织 | 主题模块为主，模块内按难度排序 |
| 排课方式 | 规则搭骨架；AI 只写模块导读与跨书对照 |
| 素材源 | 日常用本地缓存；可选从 Notion 增量同步 |
| MVP 能力 | 路径导航 + 本地进度 + 模块导读 |
| 一课形态 | 以观点为课表节点；可展开所属章节笔记 |
| 不做（本 spec） | 自测题、账号体系、公网部署、对话导师 |

## 范围

### 包含
- 从本地精读缓存加载观点与章节笔记，按固定标签组成模块课表。
- 可选 Notion 观点库增量同步，刷新本地索引（不覆盖精读章节 JSON）。
- FastAPI + Jinja 本地站点：首页 / 模块页 / 观点课页。
- AI 模块导读（可缓存）；学习进度落盘。
- 离线单元测试覆盖组课、进度、加载。

### 不包含
- 选择题自测、间隔复习算法。
- 多用户 / 登录 / 云端进度同步。
- 子项目 C 对话式导师。
- 替换或重跑子项目 A 的精读管道（只消费其产出）。

## 整体架构

```
output/.cache/{书名}/第N章.json   ← 日常主源
Notion 观点库（可选 sync）        ← 增量刷新本地索引
        │
        ▼
┌─────────────────────────────┐
│ engine/curriculum/          │
│  loader → assembler         │
│  intro_writer（AI，可缓存） │
│  progress                   │
└─────────────────────────────┘
        │
        ▼
  serve_course.py（FastAPI）
  首页 → 模块课表 → 观点课（可展开章节）
        │
        ▼
curriculum/intros/{tag}.json
curriculum/progress.json
```

要点：
- 不新建第二套笔记体系，复用 A 的 `OpinionEntry` / `ChapterNote`。
- 组课在服务端用规则完成；导读按模块缓存，学习浏览时默认不再调模型。
- 进度写入本地文件，不依赖浏览器 `localStorage`。

## 模块职责与接口

### 1. `loader`
- 输入：`output/.cache` 根目录；可选 Notion 客户端与数据库 ID。
- 输出：内存中的观点列表（带 `book_title`）+ 章节笔记索引（按书名+章节可查）。
- 行为：扫描各书章节 JSON；损坏文件跳过并打警告。
- Notion：`--sync-notion` 拉取观点库，按「书名 + 章节 + 观点标题」与本地合并；本地已有则保留章节笔记关联，仅 Notion 有的条目也可进入课表（章节笔记可能为空）。不改写 `.cache` 精读原文。合并结果可落盘 `curriculum/catalog.json` 以加快启动。

### 2. `assembler`
- 输入：观点列表 + `config.FIXED_TAGS` + `ACTIONABILITY_VALUES`。
- 输出：`Module[]`，每模块含 `tag`、有序 `Lesson[]`。
- 规则：
  - 每个固定标签一个模块；无观点的标签不展示。
  - 观点可属于多个标签 → 可出现在多个模块；进度按 lesson id 全局去重。
  - 模块内排序：`原则` → `可直接执行` → `需自己判断`；同级按书名、章节标题稳定排序。
  - **lesson id**：`{book_title}::{chapter}::{opinion_hash}`（对观点标题做稳定短哈希），用于进度与 URL。

### 3. `intro_writer`
- 输入：某模块的观点摘要列表。
- 输出：导读结构（模块目标、跨书对照要点、学习顺序说明）→ `curriculum/intros/{tag}.json`。
- 触发：首次打开该模块且无缓存时；或 CLI/`--rebuild-intros` 强制重建。
- 失败：返回规则生成的短占位文案，不阻断浏览。

### 4. `progress`
- 读写 `curriculum/progress.json`：
  - `completed`: lesson id 列表
  - `last_lesson_id`: 上次学习位置
  - `updated_at`: ISO 时间
- 损坏时：将坏文件改名为 `.bak`，从空进度恢复。

### 5. `serve_course.py`（FastAPI 入口）
- 路由（示意）：
  - `GET /` — 模块列表 + 总进度
  - `GET /module/{tag}` — 导读 + 课表
  - `GET /lesson/{lesson_id}` — 观点课；查询参数或片段展开章节笔记
  - `POST /api/progress/complete` — 标记已学
  - `GET /api/progress` — 当前进度（可选，供页面使用）
- 默认监听 `127.0.0.1:8765`。

## 页面结构

1. **首页**：各主题模块卡片（标签名、已学/总数、难度跨度提示）+ 总进度；入口「继续上次」。
2. **模块页**：AI/占位导读 + 按难度排序的观点列表（标注来源书、可执行度）。
3. **观点课页**：观点标题、论据摘要、金句、来源书/章、可执行度；按钮「展开所属章节笔记」（无章节数据时隐藏或提示不可用）；「标记已学」与「下一课」（下一课 = **当前模块课表**中的下一则，不是全局）。

UI 以清晰阅读为先，不做营销落地页式视觉；样式保持简单可读即可。

## 处理流程

### 日常学习
```
python serve_course.py
→ 浏览器打开 http://127.0.0.1:8765
→ 选模块 → 按课表学习 → 标记已学
```

### 素材更新
```
# 新书精读仍走子项目 A
python read_book.py "docs/ebook/某书.epub" --author "作者"

# 可选：从 Notion 拉观点增量到本地索引
python serve_course.py --sync-notion

# 可选：重建全部模块导读
python serve_course.py --rebuild-intros
```

## 错误处理

| 情况 | 行为 |
|---|---|
| 无本地缓存 | 首页提示先运行 `read_book.py`，服务不崩溃 |
| 某书 JSON 损坏 | 跳过该文件并日志警告，其余书照常组课 |
| 导读 AI 失败 | 模块页使用规则占位文案；可稍后重试生成 |
| Notion sync 失败 | 提示错误，继续使用本地缓存 |
| 进度文件损坏 | 备份为 `.bak`，从空进度恢复 |

## 技术选型

- **语言**：Python 3（与子项目 A 同环境）。
- **Web**：FastAPI + Jinja2Templates + 静态 CSS（少量）。
- **AI**：复用 `engine/llm.py` / `create_structured`；仅 `intro_writer` 使用。
- **配置**：复用 `config.FIXED_TAGS`、`ACTIONABILITY_VALUES`；Notion ID 仍从 `.env` 读取。
- **依赖新增**：`fastapi`、`uvicorn`、`jinja2`（写入 `requirements.txt`）。

## 测试策略

- **assembler**（离线）：假观点列表 → 模块归属、难度序、lesson id 稳定性。
- **progress**（离线）：标记已学、去重、读写与损坏恢复。
- **loader**（离线）：读测试用 cache 夹具目录。
- **HTTP 冒烟**（可选）：FastAPI `TestClient` — 首页 200；无缓存时友好提示；模块页在无导读缓存时展示占位。

不强制在 CI 中调用真实 Anthropic / Notion API。

## 与子项目 A / C 的衔接

- **A**：本站只读 `output/.cache`（及可选 Notion）；不修改精读 prompt 与 Notion 写入逻辑，除非发现字段缺口再单开变更。
- **C**：对话导师可按 lesson id / 标签检索同一批笔记；本站进度文件可供「从上次学到的模块继续问」类功能复用，但不在本 spec 实现。

## 成功标准

1. 本地已有多本精读缓存时，启动服务即可按主题浏览观点课表。
2. 模块内顺序符合可执行度难度映射，刷新后 lesson id 稳定、进度不丢。
3. 每个有内容的模块能显示导读（AI 或占位）；学习过程默认零 API 费用（除首次/重建导读）。
4. 无缓存、坏 JSON、AI/Notion 失败时均有明确降级，不导致整站不可用。
```
