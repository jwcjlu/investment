from engine.models import Chapter, ChapterNote, OpinionEntry
from engine.reader import attach_source_refs


def test_attach_source_refs_fills_offsets_from_quote_and_points():
    chapter = Chapter(
        index=1,
        title="第1章",
        text="前言。护城河决定长期回报。后记。",
    )
    note = ChapterNote(
        chapter_index=1,
        chapter_title="第1章",
        core_points=["护城河决定长期回报"],
        arguments=[],
        actionables=[],
        quotes=["护城河决定长期回报"],
        opinions=[
            OpinionEntry(
                opinion="护城河很重要",
                chapter="第1章",
                tags=["护城河/竞争优势"],
                argument_summary="长期回报",
                actionability="原则",
                quote="护城河决定长期回报",
            )
        ],
    )
    out = attach_source_refs(note, chapter, book_title="测试书")
    assert out.opinions[0].sources
    assert out.opinions[0].sources[0].char_start is not None
    assert out.core_points[0].sources
    assert chapter.text[
        out.core_points[0].sources[0].char_start : out.core_points[0].sources[0].char_end
    ] == "护城河决定长期回报"
