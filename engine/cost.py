from __future__ import annotations
from typing import List
from engine.models import Chapter
import config

# 中文近似：1 字 ≈ 1.5 token
_CHARS_TO_TOKENS = 1.5
# 输出经验值：每章输出 token 占该章输入的比例（用于全书估算）
_OUTPUT_RATIO = 0.18


def estimate_input_tokens(chapters: List[Chapter]) -> int:
    chars = sum(len(c.text) for c in chapters)
    return int(chars * _CHARS_TO_TOKENS)


def estimate_output_tokens(input_tokens: int) -> int:
    return int(input_tokens * _OUTPUT_RATIO)


def estimate_cost_usd(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens / 1_000_000 * config.PRICE_INPUT_PER_M
        + output_tokens / 1_000_000 * config.PRICE_OUTPUT_PER_M
    )


def preflight(chapters: List[Chapter]) -> dict:
    """返回估算结果，供 CLI 展示与护栏判断。"""
    in_tok = estimate_input_tokens(chapters)
    out_tok = estimate_output_tokens(in_tok)
    cost = estimate_cost_usd(in_tok, out_tok)
    return {
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "cost_usd": round(cost, 2),
        "over_threshold": cost > config.COST_ALERT_USD,
    }
