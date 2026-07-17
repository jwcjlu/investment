import pytest
from engine.llm import make_client, get_model
import config


def test_make_client_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        make_client()


def test_make_client_uses_base_url_and_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-relay-test")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://relay.example.com/v1")

    client = make_client()

    assert client.api_key == "sk-relay-test"
    assert str(client.base_url).rstrip("/") == "https://relay.example.com/v1"


def test_make_client_defaults_without_base_url(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-official")
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)

    client = make_client()

    assert client.api_key == "sk-official"
    # 官方默认 host
    assert "anthropic.com" in str(client.base_url)


def test_get_model_prefers_env_override(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
    assert get_model() == "claude-sonnet-4-5"


def test_get_model_falls_back_to_config(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    assert get_model() == config.MODEL
