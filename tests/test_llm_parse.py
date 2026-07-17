import pytest
from engine.llm import parse_json_response, extract_response_text, loads_json_loose


class _Block:
    def __init__(self, type: str, text: str = ""):
        self.type = type
        self.text = text


class _Resp:
    def __init__(self, content, stop_reason="end_turn"):
        self.content = content
        self.stop_reason = stop_reason


def test_extract_response_text_joins_text_blocks():
    resp = _Resp([_Block("thinking"), _Block("text", '{"a":1}')])
    assert extract_response_text(resp) == '{"a":1}'


def test_parse_json_response_ok():
    resp = _Resp([_Block("text", '{"core_points": ["x"]}')])
    assert parse_json_response(resp) == {"core_points": ["x"]}


def test_parse_json_response_strips_markdown_fence():
    raw = '```json\n{"ok": true}\n```'
    resp = _Resp([_Block("text", raw)])
    assert parse_json_response(resp) == {"ok": True}


def test_parse_json_response_empty_raises_with_stop_reason():
    resp = _Resp([_Block("thinking"), _Block("text", "")], stop_reason="max_tokens")
    with pytest.raises(RuntimeError, match="max_tokens"):
        parse_json_response(resp)


def test_parse_json_response_empty_fence_raises_runtime():
    resp = _Resp([_Block("text", "```json\n\n```")])
    with pytest.raises(RuntimeError, match="无法解析"):
        parse_json_response(resp)


def test_loads_json_loose_extracts_embedded_object():
    assert loads_json_loose('好的，如下：\n{"a": 1}\n完') == {"a": 1}


def test_parse_json_response_invalid_json_raises():
    resp = _Resp([_Block("text", "not-json")])
    with pytest.raises(RuntimeError, match="无法解析"):
        parse_json_response(resp)
