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
