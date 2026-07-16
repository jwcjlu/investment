import pytest
from engine.parser_pdf import parse_pdf


def _make_pdf(path):
    # 用 pypdf 无法直接写文字页；改用 reportlab 若可用，否则跳过
    reportlab = pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    # 内置 CJK 字体，保证中文能正确写入 PDF
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    c = canvas.Canvas(path)
    c.setFont("STSong-Light", 12)
    c.drawString(72, 800, "第一章 开端")
    c.drawString(72, 780, "安全边际是核心")
    c.showPage()
    c.setFont("STSong-Light", 12)
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
