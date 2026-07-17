from engine.curriculum.lesson_id import make_lesson_id, encode_lesson_id, decode_lesson_id


def test_make_lesson_id_stable():
    a = make_lesson_id("聪明的投资者", "第1章", "安全边际是核心")
    b = make_lesson_id("聪明的投资者", "第1章", "安全边际是核心")
    assert a == b
    assert a.startswith("聪明的投资者::第1章::")
    assert len(a.split("::")[-1]) == 12


def test_make_lesson_id_differs_on_opinion():
    a = make_lesson_id("书", "章", "观点甲")
    b = make_lesson_id("书", "章", "观点乙")
    assert a != b


def test_url_roundtrip():
    raw = make_lesson_id("书名", "第2章", "某观点")
    enc = encode_lesson_id(raw)
    assert "/" not in enc and " " not in enc
    assert decode_lesson_id(enc) == raw


def test_tag_roundtrip_with_slash():
    from engine.curriculum.lesson_id import encode_tag, decode_tag
    tag = "护城河/竞争优势"
    enc = encode_tag(tag)
    assert "/" not in enc
    assert decode_tag(enc) == tag
