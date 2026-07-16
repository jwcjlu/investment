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
