# 设计文档：笔记逻辑结构 · 原文索引 · 全局知识图谱

- 日期：2026-07-18
- 状态：待用户确认书面 spec
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

- 观点、金句、core_points、arguments、actionables、逻辑/图谱节点与边均可挂 `sources: SourceRef[]`。  
- 精读后处理：在对应章全文对 `excerpt` 做首次精确/规范化匹配写入偏移；失败则偏移为空，UI 降级为「仅摘录 + 打开本章」。  
- **不把全书正文塞进观点 JSON**；正文按需从解析缓存或 ebook 再解析读取。

### logic_structure（课时）

```text
LogicStructure {
  lesson_id: str
  layers: [ { level: 1|2|3, title: str, items: [LogicNodeRef] } ]
  nodes: [ KGNode ]          # 使用全局 node_id
  edges: [ KGEdge ]
  source: "ai" | "placeholder"
  generated_at: str
}
```

课时页：分层与子图置顶；原扁平列表收入「原始要点」折叠区；论据摘要保留。

### 全局知识图谱

```text
KGNode {
  node_id: str               # 全局稳定 ID
  label: str
  aliases: [str]
  kind: "concept" | "claim" | "metric" | "case" | ...
  sources: [SourceRef]
}

KGEdge {
  edge_id: str
  from: str                  # node_id
  to: str
  rel: "causes" | "contrasts" | "defines" | "evidenced_by" | ...
  sources: [SourceRef]
}
```

消歧（MVP）：规范化标签 + 可配置别名表；冲突可手工拆分，不做自动重型链接。

## 生成与溯源

输入（至少）：

- 课时原则 / 论据摘要 / 金句  
- 章节笔记包（core_points、arguments、actionables）  
- 各单元 `SourceRef.excerpt`；按需向章内前后扩展 1～2 段上下文  

约束：

- 每个逻辑节点、每条边至少一条 `SourceRef`（或明确标记 `ungrounded` 且 UI 弱化）。  
- 禁止仅对扁平列表做「看起来通顺」的重排而无摘录支撑。

混合策略：

1. **学习站按需**生成 `logic_structure`，缓存于 `curriculum/logic/`（类比 intro/quiz）。  
2. Prompt/schema 稳定后 **写回精读**管线；可选批处理为旧书补 excerpt/偏移（不强制重跑全书 AI）。

## API（增量）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/lessons/{encoded_id}/logic?tag=` | 获取或生成课时逻辑结构 |
| GET | `/api/source?book=&chapter=&start=&end=&excerpt=` | 侧栏原文片段 |
| GET | `/api/kg?q=` | M3：搜索/返回子图（M1/M2 可先内部聚合） |
| GET | `/api/modules/{tag}/kg` | M2：模块聚合子图 |

既有 `/api/lessons/...` 响应可附带 `sources`（若缓存已有）。

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
