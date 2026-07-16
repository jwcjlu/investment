import config


def test_fixed_tags_present_and_unique():
    tags = config.FIXED_TAGS
    assert "风险控制" in tags
    assert "仓位管理" in tags
    assert len(tags) == len(set(tags)), "固定标签表不应有重复"


def test_model_and_thresholds():
    assert config.MODEL == "claude-opus-4-8"
    assert config.COST_ALERT_USD > 0
    assert config.HARD_SPLIT_CHARS > 0
