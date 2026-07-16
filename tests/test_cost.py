from engine.cost import estimate_input_tokens, estimate_cost_usd
from engine.models import Chapter


def test_estimate_input_tokens_scales_with_length():
    chapters = [Chapter(index=1, title="t", text="字" * 10000)]
    tokens = estimate_input_tokens(chapters)
    # 中文约 1 字 ≈ 1.5 token，10000 字 ≈ 15000，允许合理区间
    assert 12000 <= tokens <= 20000


def test_estimate_cost_usd_uses_prices():
    # 40万 input + 7万 output（Opus: $5/$25 每百万）≈ 2 + 1.75 = 3.75
    cost = estimate_cost_usd(input_tokens=400_000, output_tokens=70_000)
    assert 3.5 <= cost <= 4.0
