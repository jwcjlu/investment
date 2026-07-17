from __future__ import annotations
import os
import sys
import argparse
from dotenv import load_dotenv

load_dotenv()  # 须先于 LLM 客户端创建，以读取中转站等配置

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
    ap.add_argument("path", help="电子书路径 (.epub/.pdf/.txt/.mobi)")
    ap.add_argument("--author", default="未知", help="作者名")
    ap.add_argument("--skip-notion", action="store_true", help="只精读+本地备份，不写 Notion")
    ap.add_argument("--yes", action="store_true", help="跳过成本确认")
    args = ap.parse_args()
    if not os.path.exists(args.path):
        print(f"文件不存在：{args.path}"); sys.exit(1)
    run(args.path, args.author, args.skip_notion, args.yes)


if __name__ == "__main__":
    main()
