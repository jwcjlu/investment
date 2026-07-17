import json
import pytest
from engine.llm import create_structured


class _Block:
    def __init__(self, type: str, text: str = ""):
        self.type = type
        self.text = text


class _Resp:
    def __init__(self, content, stop_reason="end_turn"):
        self.content = content
        self.stop_reason = stop_reason


class _FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._responses:
            raise RuntimeError("no more fake responses")
        return self._responses.pop(0)


def test_create_structured_retries_without_thinking_on_empty():
    client = _FakeClient([
        _Resp([_Block("thinking"), _Block("text", "")], stop_reason="max_tokens"),
        _Resp([_Block("text", '{"ok": true}')], stop_reason="end_turn"),
    ])
    data = create_structured(
        client,
        prompt="hi",
        schema={"type": "object"},
        max_tokens=100,
    )
    assert data == {"ok": True}
    assert len(client.calls) == 2
    assert "thinking" in client.calls[0]
    assert "thinking" not in client.calls[1]


def test_create_structured_retries_on_bad_json():
    client = _FakeClient([
        _Resp([_Block("text", "{truncated")], stop_reason="max_tokens"),
        _Resp([_Block("text", json.dumps({"a": 1}))]),
    ])
    data = create_structured(
        client,
        prompt="hi",
        schema={"type": "object"},
        max_tokens=100,
    )
    assert data == {"a": 1}


def test_create_structured_falls_back_to_raw_json_prompt():
    client = _FakeClient([
        _Resp([_Block("text", "")], stop_reason="max_tokens"),
        _Resp([_Block("text", "```json\n\n```")]),
        _Resp([_Block("text", '前缀 {"z": 9} 后缀')]),
    ])
    data = create_structured(
        client,
        prompt="hi",
        schema={"type": "object"},
        max_tokens=100,
    )
    assert data == {"z": 9}
    assert len(client.calls) == 3
    assert "output_config" not in client.calls[2]


def test_create_structured_all_fail_raises():
    client = _FakeClient([
        _Resp([_Block("text", "")]),
        _Resp([_Block("text", "")]),
        _Resp([_Block("text", "still bad")]),
    ])
    with pytest.raises(RuntimeError, match="连续失败"):
        create_structured(
            client,
            prompt="hi",
            schema={"type": "object"},
            max_tokens=100,
        )
