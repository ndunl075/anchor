"""Anthropic Messages API adapter. Raw httpx, no provider SDK (§2: zero required
deps beyond the stack table).
"""
from __future__ import annotations

import time

import httpx

from anchor.core.models import ErrorInfo, Request, Response, ToolCall, Usage
from anchor.providers.base import (
    RETRYABLE_STATUS,
    BaseProvider,
    MissingAPIKeyError,
    parse_retry_after,
    read_api_key,
)

DEFAULT_BASE_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

# params keys passed through verbatim onto the request body when present.
_PASSTHROUGH_PARAMS = ("temperature", "top_p", "top_k", "stop_sequences", "tools", "tool_choice")


class AnthropicProvider(BaseProvider):
    name = "anthropic"
    version = "1"

    def __init__(
        self,
        api_key_env: str = "ANTHROPIC_API_KEY",
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 60.0,
        client: httpx.AsyncClient | None = None,
    ):
        self.api_key_env = api_key_env
        self.base_url = base_url
        self.timeout = timeout
        self._client = client

    def supports(self, feature: str) -> bool:
        return feature in {"tools", "system", "cache"}

    def _build_payload(self, req: Request) -> dict:
        payload: dict = {
            "model": req.model,
            "messages": [{"role": m.role, "content": m.content} for m in req.messages],
            "max_tokens": req.params.get("max_tokens", 1024),
        }
        if req.system:
            payload["system"] = req.system
        for key in _PASSTHROUGH_PARAMS:
            if key in req.params:
                payload[key] = req.params[key]
        return payload

    async def _call(self, req: Request) -> Response:
        try:
            api_key = read_api_key(self.api_key_env)
        except MissingAPIKeyError as exc:
            # A missing key is a config problem, not a transient one — surface
            # it as non-retryable so generate() doesn't burn 3 backoff cycles
            # on something retrying can never fix.
            return Response(error=ErrorInfo(type="missing_api_key", message=str(exc), retryable=False))

        headers = {
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        payload = self._build_payload(req)

        client = self._client or httpx.AsyncClient(timeout=self.timeout)
        start = time.monotonic()
        try:
            http_resp = await client.post(self.base_url, json=payload, headers=headers)
        finally:
            if self._client is None:
                await client.aclose()
        latency_ms = int((time.monotonic() - start) * 1000)

        if http_resp.status_code >= 400:
            return _error_response(http_resp, latency_ms)
        return _parse_success(http_resp, req.model, latency_ms)


def _parse_success(http_resp: httpx.Response, requested_model: str, latency_ms: int) -> Response:
    data = http_resp.json()
    text = "".join(
        block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
    )
    tool_calls = [
        ToolCall(id=block["id"], name=block["name"], arguments=block.get("input", {}))
        for block in data.get("content", [])
        if block.get("type") == "tool_use"
    ]
    usage_raw = data.get("usage", {})
    usage = Usage(
        input=usage_raw.get("input_tokens", 0),
        output=usage_raw.get("output_tokens", 0),
        cache_read=usage_raw.get("cache_read_input_tokens", 0),
        cache_write=usage_raw.get("cache_creation_input_tokens", 0),
    )
    return Response(
        text=text,
        tool_calls=tool_calls,
        finish_reason=data.get("stop_reason") or "",
        usage=usage,
        latency_ms=latency_ms,
        model_resolved=data.get("model", requested_model),
        raw=data,
    )


def _error_response(http_resp: httpx.Response, latency_ms: int) -> Response:
    retryable = http_resp.status_code in RETRYABLE_STATUS
    retry_after = parse_retry_after(http_resp.headers.get("retry-after"))
    try:
        message = http_resp.json().get("error", {}).get("message", http_resp.text)
    except ValueError:
        message = http_resp.text
    return Response(
        latency_ms=latency_ms,
        error=ErrorInfo(
            type=f"http_{http_resp.status_code}",
            message=message,
            retryable=retryable,
            status_code=http_resp.status_code,
            retry_after=retry_after,
        ),
    )
