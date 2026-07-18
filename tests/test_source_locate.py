from engine.source_locate import locate_excerpt, slice_window


def test_locate_excerpt_finds_offsets():
    chapter = "前文。" + "投资资本回报率与成本之差" + "。后文。"
    start, end = locate_excerpt(chapter, "投资资本回报率与成本之差")
    assert start is not None and chapter[start:end] == "投资资本回报率与成本之差"


def test_locate_excerpt_normalizes_whitespace():
    chapter = "回报率  与成本"
    start, end = locate_excerpt(chapter, "回报率 与成本")
    assert start is not None


def test_locate_miss_returns_none():
    assert locate_excerpt("abc", "zzz") == (None, None)


def test_slice_window_includes_highlight():
    text = "a" * 100 + "TARGET" + "b" * 100
    start, end = 100, 106
    window, hi = slice_window(text, start, end, pad=20, hard_max=4000)
    assert "TARGET" in window
    assert hi is not None
    assert window[hi[0] : hi[1]] == "TARGET"
