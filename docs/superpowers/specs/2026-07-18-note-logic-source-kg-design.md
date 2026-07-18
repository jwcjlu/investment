# 设计文档：笔记逻辑结构 · 原文索引 · 全局知识图谱

- 日期：2026-07-18
- 状态：spec 复核已通过；待用户确认后进入实现计划
- 作者：与用户协作 brainstorm 产出
- 前置：
  - `docs/superpowers/specs/2026-07-16-ai-reading-investment-books-design.md`（精读引擎）
  - `docs/superpowers/specs/2026-07-17-learning-ux-enhancement-design.md`（学习站 SPA）

## 背景与目标

学习站课时页把章节「核心观点」等以**扁平列表**展示，知识点看起来孤立、缺少因果。同时精读产物只有 `书名 + chapter_index + 金句文本`，无法从笔记可靠回到书中上下文。

本 spec 目标：

1. **有逻辑的呈现** — 整页课时用「分层金字塔 + 概念关系图」组织原则、论据与章节要点。  
2. **凡笔记可回原文** — 任意笔记单元挂 `SourceRef`；学习站用**侧栏抽屉**对照阅读。  
3. **全局知识图谱** — 跨书节点/边，交付按 M1→M2→M3；schema 从第一天按全局设计。  
4. **结合书本上下文生成** — 逻辑/图谱不只重排列表，按 SourceRef 取章内上下文，且节点可溯源。

### 需求确认（来自 brainstorm）

| 维度 | 用户选择 |
|---|---|
| 目标形态 | 产品改动 + 以真实课时做样例串讲 |
| 呈现 | 分层金字塔 **且** 概念关系图 |
| 生成策略 | 混合：学习站按需验证 → 再写回精读 |
| MVP 课时表面 | **整页课时**（原则 + 论据 + 章节织进同一逻辑） |
| 原文索引范围 | **凡落笔记处**（不限原则/金句） |
| 原文展示 | **侧栏抽屉** |
| 索引实现 | 章内摘录匹配偏移；schema **预留 `para_id`** |
| 知识图谱 | **跨书全局图（C）**；交付顺序 **M1→M2→M3** |

## 范围

### 包含

- `SourceRef` 模型；精读提示词与后处理写入 excerpt / 可选偏移。  
- 学习站：`logic_structure`（分层 + 子图）按需生成与缓存；课时页 UI。  
- `GET /api/source` + 侧栏原文抽屉。  
- 知识图谱数据模型（全局 `node_id`）与三里程碑交付：  
  - **M1** SourceRef + 课时逻辑子图 + 侧栏原文  
  - **M2** 模块页聚合子图  
  - **M3** 跨书全局图谱页（搜索/点选 → 证据列表 → 抽屉/跳课时）  
- 旧缓存兼容：无 SourceRef 时隐藏「原文」；逻辑生成可降级为占位分层。  
- 相关 API / 引擎单测；前端关键路径冒烟。

### 不包含

- EPUB CFI / PDF 页码 / 外部阅读器跳转  
- 账号、云同步、多用户协作编辑图谱  
- 从全网补全概念（只用已精读的书）  
- 重型实体链接 / NLP 消歧流水线（MVP 用别名表 + 规范化）  
- 对话导师（子项目 C）本体能力（图谱可为其后置地基）

## 整体架构

```
电子书 ──► 解析章文本（可再取）
              │
              ▼
         精读 read_book
         · 笔记单元 + sources: SourceRef[]
         · 后处理：excerpt → char_start/end
              │
              ▼
         output/.cache 章节 JSON
              │
    ┌─────────┴─────────┐
    ▼                   ▼
课时 logic（按需）    全局 KG 索引
curriculum/logic/     curriculum/kg/
    │                   │
    └─────────┬─────────┘
              ▼
     SPA 课时页 / 模块页 / 图谱页
     + 侧栏抽屉 ← GET /api/source
```

## 数据模型

### SourceRef

```text
SourceRef {
  book_title: str
  chapter_index: int
  excerpt: str              # 必填：支撑原文短句
  char_start: int | null
  char_end: int | null
  para_id: str | null       # 预留，本轮可不填
}
```

规则：

- 精读后处理：在对应章全文对 `excerpt` 做首次精确/规范化匹配写入偏移；失败则偏移为空，UI 降级为「仅摘录 + 打开本章」。  
- **不把全书正文塞进观点 JSON**；正文按需从解析缓存或 ebook 再解析读取。

#### 嵌入现有章节 JSON（迁移形状，唯一方案）

列表类字段（`core_points` / `arguments` / `actionables` / 章级 `quotes`）从 `string[]` 升级为对象数组：

```text
NoteAtom {
  text: str
  sources: [SourceRef]     # 可为空数组（旧数据 normalize 后如此）
}
```

`OpinionEntry` 增加 `sources: [SourceRef]`：**挂在原则（opinion）上的证据**；`quote` 字符串字段保留。若金句需独立「原文」入口，其摘录作为 `sources` 中的一条（`excerpt` 对齐金句文本），与原则共用同一数组（MVP 不拆两个字段）。

**读取兼容（强制）：** `normalize_*` 若遇到纯字符串，转为 `{ text: s, sources: [] }`。旧缓存无「原文」按钮，但不崩溃。  
**写入：** 新精读一律写对象形。Notion 同步可继续只推 `text`/摘要字段，完整 `sources` 以本地缓存为准（本轮不要求 Notion 存偏移）。

### logic_structure（课时）

```text
LogicNodeRef { node_id: str }   # 仅引用；展示文案从 nodes[] 取

LogicStructure {
  lesson_id: str
  layers: [ { level: 1|2|3, title: str, items: [LogicNodeRef] } ]
  nodes: [ KGNode ]             # 本课时用到的节点（全局 node_id）
  edges: [ KGEdge ]
  source: "ai" | "placeholder"
  generated_at: str
}
```

分层 `items` **必须**引用 `nodes[]` 中已有 `node_id`；UI 用 `nodes` 查 label/sources。禁止在 layer 内再嵌一套游离文案节点。

课时页：分层与子图置顶；原扁平列表收入「原始要点」折叠区；论据摘要保留。

#### placeholder 降级（唯一方案）

当 AI 失败或 `enable_ai=false`：

- `source: "placeholder"`  
- `layers`：L1 = 课时原则（单节点，`sources` 拷贝自 `OpinionEntry.sources`）；L2 = 最多 5 条 `core_points` 各成节点；L3 可空  
- `edges`: `[]`（占位不编造因果）  
- 节点：`sources` 非空则 `ungrounded: false`，否则 `ungrounded: true`  
- UI：展示分层，隐藏空关系图或显示「暂无关系图」

### 全局知识图谱

```text
KGNode {
  node_id: str
  label: str
  aliases: [str]
  kind: "concept" | "claim" | "metric" | "case"   # MVP 仅此四类
  sources: [SourceRef]
  ungrounded: bool            # true 时 UI 弱化；与空 sources 同时出现于 placeholder
}

KGEdge {
  edge_id: str
  from: str
  to: str
  rel: "causes" | "contrasts" | "defines" | "evidenced_by"   # MVP 仅此四类
  sources: [SourceRef]
  ungrounded: bool
}
```

#### node_id 生成（M1 起强制，保证 M2 可合并）

1. 取 `label`，经别名表映射到**规范名**（配置文件，如 `curriculum/kg_aliases.json`；无命中则用原 label）。  
2. 规范化：NFKC、去首尾空白、合并连续空白、Unicode 小写（适用时）。  
3. `node_id = "n_" + sha1(normalized)[:12]`（稳定、与书无关）。  
4. AI **只输出 label/kind/aliases/rel**，不自造 `node_id`；由后处理按上式计算。  
5. 合并：相同 `node_id` 合并 `sources`/`aliases`；人工拆分通过别名表把错误合并的 label 映射到不同规范名（本轮不做 UI 编辑器）。  
6. `edge_id = "e_" + sha1(from + "|" + rel + "|" + to)[:12]`（与方向、关系类型相关，便于 M2 合并去重）。

消歧（MVP）：上式 + 别名表；不做重型实体链接。

## 生成与溯源

输入（至少）：

- 课时原则 / 论据摘要 / 金句  
- 章节笔记包（core_points、arguments、actionables）  
- 各单元 `SourceRef.excerpt`；按需向章内前后扩展 1～2 段上下文  

约束：

- AI 产出的节点/边：`ungrounded: false` 且 `sources` 非空；否则后处理改为 `ungrounded: true` 并清空假 sources，UI 弱化或不画该边。  
- 禁止仅对扁平列表做「看起来通顺」的重排而无摘录支撑。

混合策略：

1. **学习站按需**生成 `logic_structure`，缓存于 `curriculum/logic/{lesson_id}.json`（类比 intro/quiz）。  
2. **M2 起**在请求模块图或定时任务时，按 `node_id` 聚合写入 `curriculum/kg/modules/{encoded_tag}.json`；**M3** 维护 `curriculum/kg/global.json`（或分片索引 + 查询时合并）。M1 不强制持久化全局文件。  
3. Prompt/schema 稳定后 **写回精读**管线；可选批处理为旧书补 excerpt/偏移（不强制重跑全书 AI）。

## API（增量）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/lessons/{encoded_id}/logic?tag=` | 获取或生成课时逻辑结构 |
| GET | `/api/source` | 侧栏原文片段（见下） |
| GET | `/api/kg?q=` | M3：搜索/返回子图 |
| GET | `/api/modules/{tag}/kg` | M2：模块聚合子图 |

### `GET /api/source` 契约

查询参数：`book`（书名）、`chapter`（chapter_index）、可选 `start`/`end`、可选 `excerpt`。

成功响应：

```text
{
  book_title, chapter_index, chapter_title,
  text: str,                 # 锚点窗口：优先 [start-window, end+window]，默认前后各约 800 字，硬上限 4000 字
  highlight: { start, end } | null,   # 相对 text 的高亮区间；无偏移时用 excerpt 在 text 内再匹配，仍失败则为 null
  excerpt: str | null,
  degraded: bool             # true = 仅摘录/整章打开降级（无可靠偏移）
}
```

既有 `/api/lessons/...` 响应可附带 opinion/atoms 的 `sources`（若缓存已有）。

## UI

### 课时页（M1）

1. 原则标题与 meta  
2. **逻辑结构**：左分层金字塔 / 右（或下）关系子图  
3. 论据摘要  
4. 「原始要点」折叠（现有扁平列表）  
5. 任意带 SourceRef 的单元旁 **「原文」** → 右侧抽屉高亮 excerpt 与前后文  

### 模块页（M2）

- 导读/课表之外展示模块聚合图；点击节点 → 课时或原文抽屉。

### 全局图谱页（M3）

- 新路由（如 `/kg`）：跨书浏览与搜索；选中节点列出多书证据、关联课时；原文抽屉复用同一组件。

## 里程碑与验收

### M1

- [ ] 新精读章节 JSON 中笔记单元含 `excerpt`（及能匹配时的偏移）  
- [ ] 课时页展示分层 + 子图；节点可点出 SourceRef  
- [ ] 「原文」打开侧栏并高亮；无偏移时降级可用  
- [ ] `logic` API 有磁盘缓存与 AI 失败占位  
- [ ] 旧缓存无 SourceRef 时不崩溃  

### M2

- [ ] 同模块多课时按 `node_id` 合并出图  
- [ ] 模块页可浏览并跳转  

### M3

- [ ] 全局图谱页跨书检索节点  
- [ ] 证据列表来自多书 SourceRef，抽屉/课时跳转可用  

## 风险与对策

| 风险 | 对策 |
|---|---|
| excerpt 匹配失败/歧义 | 规范化空白；失败保留摘录；二期 `para_id` |
| AI 编造因果 | 强制 sources；无源边不展示或标弱 |
| 全局消歧错误 | 保守合并 + 别名表；可拆节点 |
| 章文本过大 | API 只返回锚点窗口，不整章塞响应 |
| 旧书无索引 | 兼容隐藏原文；可选离线补全脚本 |

## 与既有 spec 关系

- 不替代 UX enhancement；在其 SPA/API 上增量。  
- 精读 schema 变更需同步 Notion 字段策略（可先本地缓存完整、Notion 仅同步摘要字段）。  
- 下期仍可接：段落 ID 升级、原生电子书定位、导师对话检索图谱。
