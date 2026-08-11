"""OpenAI Chat Completions API adapter. Raw httpx, no provider SDK (§2)."""
from __future__ import annotations

import json
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

DEFAULT_BASE_URL = "https://api.openai.com/v1/chat/completions"

_PASSTHROUGH_PARAMS = (
    "temperature",
    "top_p",
    "max_tokens",
    "stop",
    "tools",
    "tool_choice",
    "response_format",
)


class OpenAIProvider(BaseProvider):
    name = "openai"
    version = "1"

    def __init__(
        self,
        api_key_env: str = "OPENAI_API_KEY",
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 60.0,
        client: httpx.AsyncClient | None = None,
    ):
        self.api_key_env = api_key_env
        self.base_url = base_url
        self.timeout = timeout
        self._client = client

    def supports(self, feature: str) -> bool:
        return feature in {"tools", "system", "json_mode"}

    def _build_payload(self, req: Request) -> dict:
        messages = []
        if req.system:
            messages.append({"role": "system", "content": req.system})
        messages.extend({"role": m.role, "content": m.content} for m in req.messages)
        payload: dict = {"model": req.model, "messages": messages}
        for key in _PASSTHROUGH_PARAMS:
            if key in req.params:
                payload[key] = req.params[key]
        return payload

    async def _call(self, req: Request) -> Response:
        try:
            api_key = read_api_key(self.api_key_env)
        except MissingAPIKeyError as exc:
            return Response(error=ErrorInfo(type="missing_api_key", message=str(exc), retryable=False))

        headers = {
            "Authorization": f"Bearer {api_key}",
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
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message", {})
    text = message.get("content") or ""
    tool_calls = [
        ToolCall(
            id=tc["id"],
            name=tc["function"]["name"],
            arguments=_parse_tool_args(tc["function"].get("arguments")),
        )
        for tc in (message.get("tool_calls") or [])
    ]
    usage_raw = data.get("usage", {})
    usage = Usage(
        input=usage_raw.get("prompt_tokens", 0),
        output=usage_raw.get("completion_tokens", 0),
        cache_read=(usage_raw.get("prompt_tokens_details") or {}).get("cached_tokens", 0),
        reasoning=(usage_raw.get("completion_tokens_details") or {}).get("reasoning_tokens", 0),
    )
    return Response(
        text=text,
        tool_calls=tool_calls,
        finish_reason=choice.get("finish_reason") or "",
        usage=usage,
        latency_ms=latency_ms,
        model_resolved=data.get("model", requested_model),
        raw=data,
    )


def _parse_tool_args(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"_unparsed": raw}


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
