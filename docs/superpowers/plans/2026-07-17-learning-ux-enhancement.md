# 学习路径体验增强 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 curriculum 引擎上增加每日软配额与 AI 练习缓存，并把学习站升级为 Vite/React SPA + FastAPI JSON API（导读开场、一课折叠、模块测/今日测）。

**Architecture:** Python 继续负责组课/进度/导读/出题；新增 `daily.py` 与 `quiz_writer.py`。`serve_course.py` 提供 `/api/*`；`web/` SPA 消费 API。开发期双端口；生产把 SPA build 挂到 FastAPI。

**Tech Stack:** Python 3.10+、FastAPI、现有 `engine.curriculum` / `engine.llm`、Vite + React + TypeScript + React Router、pytest、可选 Vitest。

**Spec:** `docs/superpowers/specs/2026-07-17-learning-ux-enhancement-design.md`

---

## 文件结构

```
config.py                          # + DAILY_LESSON_LIMIT = 5
engine/curriculum/
  daily.py                         # 今日清单
  quiz_writer.py                   # AI 出题 + 缓存 + 判分
serve_course.py                    # JSON API + 可选托管 SPA；Jinja 可 302
web/                               # Vite React TS SPA
  package.json
  vite.config.ts                   # proxy /api -> :8765
  src/App.tsx, main.tsx, pages/...
static/spa/                        # build 输出（gitignore 可选保留目录）
tests/
  test_daily.py
  test_quiz_writer.py
  test_api_ux.py                   # daily/quiz API 冒烟
```

**gitignore 增量：** `web/node_modules/`、`web/dist/`；`curriculum/quizzes/` 已在 `/curriculum/` 下忽略。

---

### Task 1: config + daily 引擎（TDD）

**Files:**
- Modify: `config.py`
- Create: `engine/curriculum/daily.py`
- Create: `tests/test_daily.py`

- [ ] **Step 1: 配置**

`config.py` 增加：
```python
DAILY_LESSON_LIMIT = 5
```

- [ ] **Step 2: 写失败测试 `tests/test_daily.py`**

覆盖（用假 `Module`/`Lesson`/`ProgressState`）：
1. `resolve_focus_tag(modules, progress, preferred_tag=None)` — preferred > FIXED_TAGS 首个含 last_lesson > 首个有未学原则  
2. `build_daily_list` — 最多 5 则、仅原则、跳过 completed  
3. 跨日：`date` 不同则重建，`extra_batches=0`  
4. `add_more` — 追加、`extra_batches+=1`、无可追加时 `added=0`  
5. daily.json 损坏 → 重建  

- [ ] **Step 3: 实现 `engine/curriculum/daily.py`**

关键 API：
```python
def resolve_focus_tag(modules, progress, preferred_tag: str | None = None) -> str | None: ...
def load_or_create_daily(path, modules, progress, preferred_tag=None, today=None) -> dict: ...
def add_more(path, modules, progress, limit=None) -> tuple[dict, int]:  # state, added
```

`lesson_ids` 为原始 lesson id 列表。落盘 UTF-8 JSON。

- [ ] **Step 4: pytest 通过并 commit**

```bash
python -m pytest tests/test_daily.py -v
git add config.py engine/curriculum/daily.py tests/test_daily.py
git commit -m "feat(curriculum): daily soft quota for principle lessons"
```

---

### Task 2: quiz_writer（TDD）

**Files:**
- Create: `engine/curriculum/quiz_writer.py`
- Create: `tests/test_quiz_writer.py`

- [ ] **Step 1: 失败测试**

```python
# test_placeholder_quiz_has_2_to_3_questions
# test_save_load_roundtrip
# test_get_or_create_uses_cache_without_ai (monkeypatch generate_ai_quiz)
# test_grade_submission
```

判分：`grade(quiz, answers: dict[question_id, option_index]) -> {score, details: [{id, correct, explanation}]}`

- [ ] **Step 2: 实现**

- `placeholder_quiz(module)`：2 道简易题（基于观点标题对错变形），`source=placeholder`  
- `generate_ai_quiz(module)`：`create_structured`，schema：`questions: [{id, stem, options: [str×4], answer_index: int, explanation}]`，长度 2–3  
- `get_or_create_quiz(module, quizzes_dir, use_ai=True, force=False)`  
- 文件名：`safe_tag = tag.replace("/", "_")` → `curriculum/quizzes/{safe_tag}.json`  
- AI 失败 → 占位题并保存  

- [ ] **Step 3: commit**

```bash
git add engine/curriculum/quiz_writer.py tests/test_quiz_writer.py
git commit -m "feat(curriculum): AI quiz generation with disk cache"
```

---

### Task 3: FastAPI JSON API

**Files:**
- Modify: `serve_course.py`
- Create: `tests/test_api_ux.py`
- Keep Jinja routes temporarily **or** redirect `/` HTML to SPA later (Task 6)；本 Task 先加 `/api/*` 不删旧页。

- [ ] **Step 1: 失败测试（TestClient）**

夹具 cache + tmp curriculum_dir，`enable_ai_intro=False`：
- `GET /api/modules` → 200，含模块；空 cache 时友好字段/空列表  
- `GET /api/daily` → `lesson_ids` 长度 ≤ 5；响应含 `tag`、`extra_batches`、每课展示字段（opinion 摘要等）  
- `GET /api/daily?tag=` → 焦点为指定 tag  
- `POST /api/daily/more` → 含 `added`；刷完时 `added: 0`  
- `GET /api/quiz?tag=`（encode，含 slash tag）→ questions 非空（占位）  
- `GET /api/quiz?daily=1` → 使用 daily.json 的 tag 题库  
- `GET /api/quiz?tag=&force=1` → 可强制重建（mock AI）  
- `POST /api/quiz/submit` body `{ "tag": "...", "answers": { "q1": 0 } }` → 返回 score + details  

- [ ] **Step 2: 实现路由**

在 `create_app` 中注册（注意 slash tag 用 `{encoded_tag:path}`）：
- 现有 progress API 保留并挂到 `/api/progress`  
- 新：`/api/modules`、`/api/modules/{encoded_tag:path}`、`/api/lessons/{encoded_id}`（query `tag` 必填）、`/api/daily`、`/api/daily/more`、`/api/quiz`、`/api/quiz/submit`  
- 模块详情含 intro（`get_or_create_intro`）+ `encoded_tag`  
- lesson 响应含：`encoded_id`、`argument_summary`、`quote`、章节笔记字段、`next_lesson_id`、`next_encoded_id`（同 tag 模块内）  
- `GET /api/quiz?daily=1`：读 `daily.json.tag` 再 `get_or_create_quiz`  
- CLI 增加 `--rebuild-quizzes`  

序列化：dataclass → dict；**一律附带 `encoded_tag` / `encoded_id`** 供 SPA 使用。

- [ ] **Step 3: commit**

```bash
git add serve_course.py tests/test_api_ux.py
git commit -m "feat: expose JSON API for SPA learning UX"
```

---

### Task 4: 脚手架 web/（Vite React TS）

**Files:**
- Create: `web/` 全套脚手架  
- Modify: `.gitignore`（`web/node_modules/`、`web/dist/`）

- [ ] **Step 1: 创建项目**

```bash
mkdir web
cd web
npm create vite@latest . -- --template react-ts
npm install
npm install react-router-dom
```

`vite.config.ts`：
```ts
server: { proxy: { '/api': 'http://127.0.0.1:8765' } }
```

- [ ] **Step 2: 最小 App 路由骨架**

**Slash tag（必做）：** 不要用 `/module/:tag`（单段）。使用 React Router splat：
- `/module/*` → `const tag = useParams()['*']`（已是解码后的 tag，或再 `decodeURIComponent`）
- `/lesson/:id` 的 `id` 用 `encodeURIComponent(encoded_id from API)`；query 必带 `?tag=`

路由：`/`、`/module/*`、`/lesson/:id`、`/quiz`  
`src/api.ts`：`fetch` 封装 `getModules`、`getDaily`、`getQuiz({tag}|{daily:true})` 等。

- [ ] **Step 3: commit**

```bash
git add web .gitignore
git commit -m "chore: scaffold Vite React SPA for learning site"
```

（勿提交 `node_modules`。）

---

### Task 5: SPA 页面实现（1–4 体验）

**Files:**
- Create/Modify: `web/src/pages/HomePage.tsx`、`ModulePage.tsx`、`LessonPage.tsx`、`QuizPage.tsx`  
- Create: `web/src/styles.css`（简洁可读）

- [ ] **Step 1: HomePage**

今日清单、再学 5 则、继续上次、模块卡片、清单完成 →「去做今日小测」。

- [ ] **Step 2: ModulePage**

导读置顶；课表；「开始练习」→ `/quiz?tag=`。  
链接课页：`/lesson/${encodeURIComponent(id)}?tag=${encodeURIComponent(tag)}`（与后端 encode 规则对齐：优先复用后端返回的 `encoded_id` / `encoded_tag` 字段，避免前后端各编一套）。

- [ ] **Step 3: LessonPage**

默认显示观点+摘要+元数据；`<details>` 折叠金句与章节笔记；标记已学；下一课带 tag。

- [ ] **Step 4: QuizPage**

拉题、选题、提交、展示解析；支持 `tag` 与 `daily=1`。

- [ ] **Step 5: 手动冒烟**

```bash
# 终端1
python serve_course.py --no-ai-intro --port 8765
# 终端2
cd web && npm run dev
```

打开 Vite URL，走通：今日 → 一课折叠 → more → 小测。

- [ ] **Step 6: commit**

```bash
git add web/src
git commit -m "feat(web): learning UX pages for daily, lessons, quizzes"
```

---

### Task 6: 生产托管 SPA + README

**Files:**
- Modify: `serve_course.py` — 挂载 `static/spa`（若存在）；未匹配 API 时回退 `index.html`（SPA history）  
- Modify: `README.md`  
- Modify: spec 状态为已实现计划就绪（可选）  
- Optional: Jinja `/` 302 到 `/app/` 或直接以 SPA 为主  

- [ ] **Step 1: build 脚本约定**

`web/package.json`：
```json
"build": "tsc -b && vite build --outDir ../static/spa --emptyOutDir"
```

- [ ] **Step 2: FastAPI 托管（主路径 = SPA）**

若 `static/spa/index.html` 存在：
1. **禁用/移除** Jinja HTML 路由（`/`、`/module/...`、`/lesson/...`），或统一 302 到 SPA 等价路径；不得继续渲染旧 Jinja 首页。  
2. `app.mount("/assets", StaticFiles(...))` 等按 Vite build 结构挂载。  
3. catch-all `GET /{full_path:path}`：非 `/api` 前缀时返回 `spa/index.html`（注册顺序在 `/api` 之后）。  
4. 保留现有 `/static`（旧 CSS）不覆盖 SPA assets。  

若尚无 build：可临时保留 Jinja，但 README 写明须先 `npm run build`。  
开发仍用 Vite proxy。

- [ ] **Step 3: README**

更新「学习路径网站」：
```bash
# 开发
python serve_course.py --no-ai-intro --port 8765
cd web && npm run dev

# 一键（先 build）
cd web && npm run build
python serve_course.py --no-ai-intro
# 打开 http://127.0.0.1:8765
```

- [ ] **Step 4: 全量测试**

```bash
python -m pytest -q
```

- [ ] **Step 5: commit**

```bash
git add serve_course.py README.md web/package.json
git commit -m "feat: serve SPA build from FastAPI and document UX workflow"
```

---

## 实现注意

1. Windows：commit 用 `git commit -m` 双段，不用 bash heredoc。  
2. lesson / module 的 URL 编码与后端 `encode_tag` / `encode_lesson_id` 一致；**API 响应带上 encoded 字段**，前端少自编。  
3. 默认 `--no-ai-intro` 测试；出题测试一律 mock。  
4. 不做账号/云同步/SRS/导师。  

## 完成定义

- [ ] Task 1–6 完成，pytest 全绿  
- [ ] SPA 可完成今日清单 → 折叠课 → 再学 5 则 → 今日小测  
- [ ] 模块导读在课表之上；开始练习可用  
- [ ] README 含开发与 build 启动说明  
