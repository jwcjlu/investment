# 设计文档：学习路径体验增强（SPA + 导读/拆短/练习/每日节奏）

- 日期：2026-07-17
- 状态：待用户复核 spec
- 作者：与用户协作 brainstorm 产出
- 前置：`docs/superpowers/specs/2026-07-17-learning-path-website-design.md`（子项目 B MVP）

## 背景与目标

子项目 B 的本地学习站已能按主题/难度浏览观点课，但体验偏「知识库列表」：一课信息过满、缺少开场与节奏、没有巩固练习，学起来容易枯燥。

本 spec 在 **不重做精读引擎** 的前提下，增强学习体验：

1. **模块导读开场** — 进模块先读导读，再进课表  
2. **一课拆短** — 默认只看观点+论据摘要；金句/章节笔记折叠  
3. **AI 小练习** — 每模块 2～3 道选择题，结果缓存  
4. **每日软配额** — 默认每日 5 则「原则」；可「再学 5 则」；完成后引导今日小测  

交付形态选用 **方案 3**：Vite + React + TypeScript SPA + FastAPI JSON API（组课/进度/出题仍在 Python）。

### 需求确认（来自 brainstorm）

| 维度 | 用户选择 |
|---|---|
| 范围 | 1+2+3+4 同一份 spec |
| 出题 | AI 生成 + 磁盘缓存 |
| 每日节奏 | 软配额（默认 5 则原则，可追加；不锁死自由浏览） |
| 练习入口 | 模块旁随时可测 **且** 今日清单完成后引导今日小测 |
| 架构 | SPA 前端 + FastAPI API |
| 本 spec 不做、写入下期规划 | 账号、云同步、间隔复习、对话导师（子项目 C） |

## 范围

### 包含
- 将现有 Jinja 站点升级为：API 后端 + `web/` SPA（开发双端口；生产可由 FastAPI 托管 build 产物）。
- 强化模块导读为首屏开场；观点课默认折叠次要内容。
- `quiz_writer`：按模块生成选择题并缓存；模块测 + 今日测入口。
- `daily`：基于进度与焦点模块生成今日清单；软配额与「再学 5 则」。
- 后端单测（daily / quiz 缓存与判分）；前端可选冒烟。

### 不包含（下期规划，见文末）
- 用户账号与登录  
- 进度/清单云同步  
- 间隔复习（SRS）算法  
- 对话式投资导师（子项目 C）  

## 整体架构

```
web/（Vite + React + TS）
  /                今日清单 + 模块入口
  /module/:tag     导读开场 + 课表 +「开始练习」
  /lesson/:id      拆短观点课
  /quiz            模块测 / 今日测
        │  /api/*
        ▼
serve_course.py（FastAPI JSON API）
  engine/curriculum/   loader · assembler · progress · intro_writer
  + daily.py           今日软配额
  + quiz_writer.py     AI 出题 + 缓存
        │
        ▼
output/.cache/
curriculum/
  progress.json
  intros/{tag}.json
  quizzes/{tag}.json
  daily.json
```

要点：
- Python 继续负责组课、进度、导读、出题；SPA 只消费 JSON、负责交互。  
- 开发：`uvicorn`（如 `:8765`）+ `vite`（如 `:5173`，代理 `/api`）。  
- 本机一键学：`npm run build` 产物进 `static/spa/`（或约定目录），FastAPI 挂载；`python serve_course.py` 仍可打开完整站。  
- 旧 Jinja HTML 路由：可保留兼容或 302 到 SPA；**主路径是 SPA**。

## 功能设计

### 1. 模块导读开场
- 模块页首屏为导读区（goals / cross_book / study_order_note），来自现有 `get_or_create_intro`。  
- 导读下方为课表；「开始练习」与课表标题同行或紧邻。  
- 无 AI 缓存时仍显示占位导读，不挡浏览。

### 2. 一课拆短
观点课默认展示：
- 观点标题  
- 论据摘要  
- 来源书 / 章节 / 可执行度  

默认折叠：
- 原文金句  
- 所属章节笔记  

「标记已学」「下一课」（当前模块内）始终可见。

### 3. AI 小练习
- 每套 **2～3** 道单选题；每题 4 选项 + 简短解析。  
- 生成输入：该模块观点摘要（题干不得照抄唯一金句当唯一答案线索时可放宽，但须忠于笔记）。  
- 缓存：`curriculum/quizzes/{safe_tag}.json`；`--rebuild-quizzes` 或 API `force=1` 可重建。  
- 入口：  
  - **模块测**：`GET /api/quiz?tag=` → SPA `/quiz?tag=`  
  - **今日测**：完成今日清单后引导；`GET /api/quiz?daily=1`（从今日课涉及的标签抽题或合并当日焦点模块题集；MVP 可简化为：用今日清单所属焦点模块的题库）。  
- `POST /api/quiz/submit`：提交选项，返回对错与解析；可选写入 `progress` 旁的 quiz 成绩字段（YAGNI：MVP 只返回结果，不强制存历史）。

### 4. 每日软配额
- 焦点模块：`progress.last_lesson_id` 所属模块；否则第一个仍有未学「原则」的模块。  
- 每日从焦点模块取最多 **5** 则：`actionability == 原则` 且未在 `completed` 中。  
- 状态文件 `curriculum/daily.json`：`{ date, tag, lesson_ids, extra_batches }`。跨自然日自动重建。  
- `POST /api/daily/more`：再追加最多 5 则未学原则（同规则）。  
- **不**拦截用户进入其它模块自由学习；首页优先展示今日清单。  
- 今日清单全部标记已学后，SPA 显示「去做今日小测」CTA。

## API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/modules` | 模块列表 + 进度 |
| GET | `/api/modules/{encoded_tag}` | 导读 + 课表（tag 含 `/` 时用 path/编码规则，与现站一致） |
| GET | `/api/lessons/{encoded_id}?tag=` | 观点课 + 可选章节 |
| POST | `/api/progress/complete` | `{ lesson_id }` |
| GET | `/api/progress` | 进度 JSON |
| GET | `/api/daily` | 今日清单 |
| POST | `/api/daily/more` | 再学 5 则 |
| GET | `/api/quiz?tag=` / `?daily=1` | 取题（可触发 AI） |
| POST | `/api/quiz/submit` | 交卷判分 |

## 前端页面

| 路由 | 内容 |
|---|---|
| `/` | 今日清单、再学 5 则、模块卡片入口、完成后今日小测 CTA |
| `/module/:tag` | 导读开场 + 课表 + 开始练习 |
| `/lesson/:id` | 拆短课页 |
| `/quiz` | 答题 UI（模块 / 每日） |

视觉：清晰阅读向，少装饰；不用营销落地页式布局。

## 错误处理

| 情况 | 行为 |
|---|---|
| 无本地缓存 | API/首页提示先跑 `read_book.py` |
| 导读/出题 AI 失败 | 占位文案或简易占位题；不阻断浏览与清单 |
| daily.json 损坏 | 按当日规则重建 |
| quiz 缓存损坏 | 删除坏文件并按需重建 |

## 技术选型

- **后端**：现有 FastAPI；新增 `engine/curriculum/daily.py`、`quiz_writer.py`；复用 `engine.llm.create_structured`。  
- **前端**：`web/` 下 Vite + React + TypeScript；React Router。  
- **配置**：每日默认条数可进 `config.py`（如 `DAILY_LESSON_LIMIT = 5`）。  
- **依赖**：后端不变为主；前端 `package.json` 独立。

## 测试策略

- **daily**：给定假模块+进度 → 清单条数、只含原则、跨日重建、more 追加。  
- **quiz_writer**：缓存命中不调 AI；submit 判分正确（mock `generate_quiz`）。  
- **API**：TestClient 冒烟（daily / quiz）。  
- **前端**：可选 Vitest 路由/折叠组件；不强制 E2E。

## 成功标准

1. SPA 可完成：看今日清单 → 学完一课（折叠交互）→ 再学 5 则 → 今日小测。  
2. 模块页导读在课表之上；「开始练习」可进入模块测。  
3. 观点课默认不铺开整章笔记。  
4. 学习浏览默认不烧 API；首次导读/出题才调用模型。  
5. 无账号情况下进度与每日清单本机持久化可用。

## 下期规划（明确不在本 spec）

以下能力另开 brainstorm / spec，本实现不做：

| 主题 | 说明 |
|---|---|
| **账号体系** | 多用户或本机登录态（若需要） |
| **云同步** | 进度 / 每日清单 / 练习成绩同步到云端或 Notion |
| **间隔复习算法** | 基于遗忘曲线的复习队列（SRS） |
| **对话式投资导师（子项目 C）** | 基于同一批笔记的检索问答 / 陪练对话 |

本 spec 完成后，学习站应先达到「不那么枯燥的可日更学习流」；再叠加下期能力。
