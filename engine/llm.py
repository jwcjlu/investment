from __future__ import annotations
import json
import os
import re
from typing import Any, Optional

from anthropic import Anthropic
import config


def make_client() -> Anthropic:
    """创建 Anthropic 客户端；支持中转站 ANTHROPIC_BASE_URL。"""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "未设置 ANTHROPIC_API_KEY。请复制 .env.example 为 .env 并填入密钥后重试。"
        )
    kwargs: dict = {"api_key": api_key}
    base_url = os.environ.get("ANTHROPIC_BASE_URL", "").strip()
    if base_url:
        kwargs["base_url"] = base_url.rstrip("/")
    return Anthropic(**kwargs)


def get_model() -> str:
    """模型名：优先 ANTHROPIC_MODEL，否则用 config.MODEL。"""
    return os.environ.get("ANTHROPIC_MODEL", "").strip() or config.MODEL


def extract_response_text(resp: Any) -> str:
    """拼接所有 type=text 的内容块。"""
    parts = []
    for block in getattr(resp, "content", []) or []:
        if getattr(block, "type", None) == "text":
            parts.append(getattr(block, "text", "") or "")
    return "".join(parts).strip()


_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", re.DOTALL | re.IGNORECASE)


def loads_json_loose(text: str) -> dict:
    """解析模型返回的 JSON，容忍 markdown 围栏与前后废话。"""
    text = (text or "").strip()
    if not text:
        raise json.JSONDecodeError("Expecting value", text, 0)

    m = _FENCE_RE.match(text)
    if m:
        text = m.group(1).strip()

    # 去掉 BOM / 零宽字符
    text = text.lstrip("\ufeff\u200b\u200c\u200d").strip()
    if not text:
        raise json.JSONDecodeError("Expecting value", text, 0)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # 从首个 { 到最后一个 } 截取
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise
        data = json.loads(text[start : end + 1])

    if not isinstance(data, dict):
        raise ValueError(f"期望 JSON 对象，实际为 {type(data).__name__}")
    return data


def parse_json_response(resp: Any) -> dict:
    """从 Messages 响应中解析 JSON；空文本时给出可诊断错误。"""
    text = extract_response_text(resp)
    if not text:
        types = [getattr(b, "type", "?") for b in (getattr(resp, "content", []) or [])]
        raise RuntimeError(
            f"模型返回空文本（stop_reason={getattr(resp, 'stop_reason', None)}, "
            f"content_types={types}）。通常是 thinking 耗尽了 max_tokens。"
        )
    try:
        return loads_json_loose(text)
    except (json.JSONDecodeError, ValueError) as e:
        preview = text[:300].replace("\n", "\\n")
        raise RuntimeError(
            f"无法解析模型 JSON（stop_reason={getattr(resp, 'stop_reason', None)}）："
            f"{e}; preview={preview!r}"
        ) from e


def _debug_dump(resp: Any, label: str) -> None:
    """把失败响应当地落盘，便于排查中转站异常。"""
    try:
        os.makedirs(os.path.join("output", ".cache"), exist_ok=True)
        path = os.path.join("output", ".cache", "_last_llm_failure.txt")
        types = [getattr(b, "type", "?") for b in (getattr(resp, "content", []) or [])]
        text = extract_response_text(resp)
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"label={label}\n")
            f.write(f"stop_reason={getattr(resp, 'stop_reason', None)}\n")
            f.write(f"content_types={types}\n")
            f.write("--- text ---\n")
            f.write(text if text else "<empty>\n")
    except OSError:
        pass


def create_structured(
    client: Anthropic,
    *,
    prompt: str,
    schema: dict,
    max_tokens: int,
    use_thinking: bool = True,
) -> dict:
    """
    调用模型并解析结构化 JSON。
    失败时按序降级重试：关 thinking → 关 schema 约束。
    """
    attempts = []
    if use_thinking:
        attempts.append({"thinking": True, "schema": True, "label": "thinking+schema"})
    attempts.append({"thinking": False, "schema": True, "label": "no-thinking+schema"})
    attempts.append({"thinking": False, "schema": False, "label": "no-thinking+raw-json"})

    last_err: Optional[Exception] = None
    last_resp = None

    for i, attempt in enumerate(attempts):
        kwargs: dict = {
            "model": get_model(),
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if attempt["thinking"]:
            kwargs["thinking"] = {"type": "adaptive"}
        if attempt["schema"]:
            kwargs["output_config"] = {
                "format": {"type": "json_schema", "schema": schema}
            }
        else:
            # 中转站若不支持 output_config，退回纯提示词约束
            kwargs["messages"] = [{
                "role": "user",
                "content": prompt + "\n\n请只输出一个合法 JSON 对象，不要 markdown，不要解释。",
            }]

        resp = None
        try:
            resp = client.messages.create(**kwargs)
            last_resp = resp
            return parse_json_response(resp)
        except Exception as e:
            last_err = e
            if resp is not None:
                _debug_dump(resp, attempt["label"])
                last_resp = resp
            if i + 1 < len(attempts):
                print(f"      警告：LLM 输出异常（{attempt['label']}），降级重试…")
                continue
            break

    if last_resp is not None:
        _debug_dump(last_resp, "final")
    raise RuntimeError(f"结构化输出连续失败：{last_err}") from last_err
