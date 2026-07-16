from engine.models import Chapter, ChapterNote, OpinionEntry, BookSummary


def test_chapter_roundtrip():
    ch = Chapter(index=1, title="第一章", text="正文")
    assert ch.index == 1
    assert ch.title == "第一章"


def test_chapter_note_to_from_dict():
    note = ChapterNote(
        chapter_index=1,
        chapter_title="第一章",
        core_points=["观点A"],
        arguments=["论据A"],
        actionables=["要点A"],
        quotes=["金句A"],
        opinions=[
            OpinionEntry(
                opinion="永远不要满仓单一标的",
                chapter="第一章",
                tags=["风险控制", "仓位管理"],
                argument_summary="集中导致不可控回撤",
                actionability="原则",
                quote="不要把鸡蛋放在一个篮子里",
            )
        ],
        suggested_tags=[],
    )
    d = note.to_dict()
    restored = ChapterNote.from_dict(d)
    assert restored == note
    assert restored.opinions[0].tags == ["风险控制", "仓位管理"]


def test_book_summary_fields():
    s = BookSummary(
        book_title="聪明的投资者",
        author="格雷厄姆",
        one_liner="价值投资奠基之作",
        core_theses=["安全边际", "市场先生"],
        principles=["坚持安全边际"],
        open_questions=["如何估算内在价值需自己判断"],
    )
    assert s.author == "格雷厄姆"
    assert len(s.core_theses) == 2
