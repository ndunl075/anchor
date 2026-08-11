"""Provider adapters (§5.1): success parsing, error classification, retry
policy, and the missing-key non-retryable path. All against httpx.MockTransport
— no live calls, per §11.
"""
from __future__ import annotations

import httpx
import pytest

from anchor.core.models import Message, Request
from anchor.providers.anthropic import AnthropicProvider
from anchor.providers.openai import OpenAIProvider
from anchor.providers.openai_compat import OpenAICompatProvider


@pytest.fixture(autouse=True)
def api_keys(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("OPENAI_API_KEY", "test")


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def _generate(provider, model="m"):
    req = Request(model=model, messages=[Message(role="user", content="hey")])
    return await provider.generate(req)


async def test_anthropic_success():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "hi"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 3, "output_tokens": 2},
                "model": "claude-opus-5",
            },
        )

    provider = AnthropicProvider(client=_client(handler))
    resp = await _generate(provider)
    assert resp.text == "hi"
    assert resp.usage.input == 3 and resp.usage.output == 2
    assert resp.model_resolved == "claude-opus-5"
    assert resp.error is None


async def test_anthropic_tool_call_parsing():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "content": [{"type": "tool_use", "id": "t1", "name": "lookup", "input": {"q": "x"}}],
                "stop_reason": "tool_use",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    provider = AnthropicProvider(client=_client(handler))
    resp = await _generate(provider)
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "lookup"
    assert resp.tool_calls[0].arguments == {"q": "x"}


async def test_anthropic_4xx_is_not_retried():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(400, json={"error": {"message": "bad request"}})

    provider = AnthropicProvider(client=_client(handler))
    resp = await _generate(provider)
    assert resp.error is not None
    assert resp.error.retryable is False
    assert calls["n"] == 1


async def test_anthropic_429_retries_then_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(429, json={"error": {"message": "rate limited"}})
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "ok"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    provider = AnthropicProvider(client=_client(handler))
    provider.base_delay = 0.01  # keep the test fast
    resp = await _generate(provider)
    assert resp.text == "ok"
    assert calls["n"] == 2


async def test_missing_api_key_is_not_retried(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    def handler(request):
        raise AssertionError("should never reach the network without a key")

    provider = AnthropicProvider(client=_client(handler))
    resp = await _generate(provider)
    assert resp.error is not None
    assert resp.error.type == "missing_api_key"
    assert resp.error.retryable is False


async def test_openai_success():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "hi there"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 2},
                "model": "gpt-5",
            },
        )

    provider = OpenAIProvider(client=_client(handler))
    resp = await _generate(provider)
    assert resp.text == "hi there"
    assert resp.usage.input == 4 and resp.usage.output == 2


async def test_openai_tool_call_parsing():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {"id": "t1", "function": {"name": "lookup", "arguments": '{"q": "x"}'}}
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    provider = OpenAIProvider(client=_client(handler))
    resp = await _generate(provider)
    assert resp.text == ""
    assert resp.tool_calls[0].arguments == {"q": "x"}


async def test_openai_compat_works_without_an_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    def handler(request):
        assert request.url.path == "/v1/chat/completions"
        assert "authorization" not in request.headers
        return httpx.Response(200, json={"choices": [{"message": {"content": "local"}, "finish_reason": "stop"}]})
    resp = await _generate(OpenAICompatProvider(client=_client(handler)))
    assert resp.text == "local"
