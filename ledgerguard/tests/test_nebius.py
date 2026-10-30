"""Offline tests for the Nebius Token Factory (NVIDIA Nemotron) preset."""

from __future__ import annotations

import json

import httpx
import pytest

from ledgerguard.ai.errors import ProviderNotConfigured
from ledgerguard.ai.provider import get_provider


@pytest.fixture
def nebius_env(monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "placeholder-not-a-real-key")
    monkeypatch.delenv("LEDGERGUARD_MODEL", raising=False)
    monkeypatch.delenv("LEDGERGUARD_REASONING_EFFORT", raising=False)


def test_nebius_preset_targets_token_factory_and_nemotron(nebius_env):
    provider = get_provider("nebius")

    assert provider.base_url == "https://api.tokenfactory.nebius.com/v1"
    assert provider.model == "nvidia/Nemotron-3_5-Lightning"
    assert all(m.startswith("nvidia/") for m in provider.models)
    assert provider.name == "nebius:nvidia/Nemotron-3_5-Lightning"


def test_model_is_overridable(nebius_env, monkeypatch):
    monkeypatch.setenv("LEDGERGUARD_MODEL", "nvidia/some-other-nemotron")

    assert get_provider("nebius").models == ["nvidia/some-other-nemotron"]


def test_named_nebius_without_a_key_is_an_error_not_a_stub(monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)

    with pytest.raises(ProviderNotConfigured):
        get_provider("nebius")


def test_request_shape_and_reasoning_output_parse(nebius_env):
    provider = get_provider("nebius")
    answer = {
        "hypothesis": "insufficient_evidence",
        "reason": "No linked refund.",
        "required_evidence": [],
        "candidate_evidence_ids": [],
        "recommended_action": "review",
    }
    sent = {}

    class FakeClient:
        def post(self, url, **kwargs):
            sent.update(url=url, **kwargs)
            return httpx.Response(
                200,
                json={
                    "model": "nvidia/Nemotron-3_5-Lightning",
                    # Thinking left in the content ahead of the answer.
                    "choices": [{"message": {"content": "<think>check linkage</think>\n"
                                             + json.dumps(answer)}}],
                },
                request=httpx.Request("POST", url),
            )

    provider._client = FakeClient()
    result = provider.investigate({"case": "nebius"})

    assert sent["url"] == "https://api.tokenfactory.nebius.com/v1/chat/completions"
    assert sent["headers"]["Authorization"] == "Bearer placeholder-not-a-real-key"
    assert sent["json"]["model"] == "nvidia/Nemotron-3_5-Lightning"
    assert sent["json"]["response_format"] == {"type": "json_object"}
    assert result.source == "model"
    assert result.model_name == "nvidia/Nemotron-3_5-Lightning"
    assert result.hypothesis == "insufficient_evidence"
