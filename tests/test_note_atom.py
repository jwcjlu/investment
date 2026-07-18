from engine.models import NoteAtom, SourceRef, OpinionEntry, ChapterNote


def test_note_atom_from_plain_string():
    atom = NoteAtom.from_any("护城河很重要")
    assert atom.text == "护城河很重要"
    assert atom.sources == []


def test_chapter_note_loads_legacy_string_lists():
    note = ChapterNote.from_dict(
        {
            "chapter_index": 1,
            "chapter_title": "第1章",
            "core_points": ["a"],
            "arguments": ["b"],
            "actionables": ["c"],
            "quotes": ["q"],
            "opinions": [
                {
                    "opinion": "原则",
                    "chapter": "第1章",
                    "tags": ["估值"],
                    "argument_summary": "论据",
                    "actionability": "原则",
                    "quote": "金句",
                }
            ],
        }
    )
    assert note.core_points[0].text == "a"
    assert note.opinions[0].sources == []


def test_opinion_roundtrip_with_sources():
    op = OpinionEntry(
        opinion="原则",
        chapter="第1章",
        tags=["估值"],
        argument_summary="论据",
        actionability="原则",
        quote="金句",
        sources=[
            SourceRef(
                book_title="书",
                chapter_index=1,
                excerpt="金句",
                char_start=10,
                char_end=12,
            )
        ],
    )
    restored = OpinionEntry.from_dict(op.to_dict())
    assert restored.sources[0].excerpt == "金句"
    assert restored.sources[0].char_start == 10
