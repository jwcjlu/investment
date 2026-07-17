# AI 精读投资书籍 → Notion 笔记引擎

把电子书逐章喂给 Claude Opus 4.8 精读，产出结构化笔记，写入 Notion（总览页面 + 可跨书检索的观点数据库），并在本地留 Markdown 备份。

## 安装
1. 安装依赖：`pip install -r requirements.txt`
2. 复制 `.env.example` 为 `.env`，填入：
   - `ANTHROPIC_API_KEY`（中转站或官方 key）
   - `ANTHROPIC_BASE_URL`（中转站地址；走官方 API 可省略）
   - `ANTHROPIC_MODEL`（可选，中转站模型名与官方不一致时再填）
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
# 也支持 .pdf / .txt / .mobi（未加密）
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
