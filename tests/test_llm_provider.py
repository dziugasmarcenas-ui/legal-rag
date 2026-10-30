"""Provider selection is configuration, so it is testable without a network call.

The generation itself is not tested here -- it costs money and its quality is a
separate question. What is tested is the seam: which provider gets picked, which
model name is reported, and that an unknown provider fails loudly instead of
silently answering from the wrong place.
"""

import sys

from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

import llm


def test_openai_is_the_default(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert llm.provider() == "openai"


def test_provider_and_model_are_read_at_call_time(monkeypatch):
    """main.py loads .env after importing llm, so import-time reads would lose it."""
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_ANSWER_MODEL", "claude-sonnet-5")
    assert llm.provider() == "anthropic"
    assert llm.model_name() == "claude-sonnet-5"


def test_each_provider_has_a_default_model(monkeypatch):
    for name in ("openai", "anthropic"):
        monkeypatch.delenv(llm.MODEL_ENV[name], raising=False)
        assert llm.model_name(name) == llm.DEFAULTS[name]


def test_every_provider_can_name_its_api_key(monkeypatch):
    """A provider without a key name would fail at request time, not at startup."""
    assert set(llm.DEFAULTS) == set(llm.MODEL_ENV) == set(llm.API_KEY_ENV)


def test_unknown_provider_fails_loudly(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "definitely-not-a-provider")
    with pytest.raises(ValueError, match="LLM_PROVIDER"):
        llm.generate("prompt")
