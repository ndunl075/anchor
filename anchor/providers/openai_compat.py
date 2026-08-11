"""OpenAI Chat Completions-compatible provider for Ollama, vLLM and gateways."""
from __future__ import annotations

import os
import time

import httpx

from anchor.core.models import ErrorInfo, Request, Response
from anchor.providers.openai import OpenAIProvider, _error_response, _parse_success


class OpenAICompatProvider(OpenAIProvider):
    name = "openai_compat"
    version = "1"

    def __init__(self, api_key_env: str = "OPENAI_API_KEY", base_url: str = "http://localhost:11434/v1", timeout: float = 60.0, client: httpx.AsyncClient | None = None):
        super().__init__(api_key_env=api_key_env, base_url=base_url.rstrip("/") + "/chat/completions", timeout=timeout, client=client)

    async def _call(self, req: Request) -> Response:
        # Local-compatible servers commonly accept no Authorization header.
        headers = {"content-type": "application/json"}
        if key := os.environ.get(self.api_key_env):
            headers["Authorization"] = f"Bearer {key}"
        client = self._client or httpx.AsyncClient(timeout=self.timeout)
        start = time.monotonic()
        try:
            http_resp = await client.post(self.base_url, json=self._build_payload(req), headers=headers)
        except Exception as exc:
            return Response(error=ErrorInfo(type=type(exc).__name__, message=str(exc), retryable=True))
        finally:
            if self._client is None:
                await client.aclose()
        latency_ms = int((time.monotonic() - start) * 1000)
        return _error_response(http_resp, latency_ms) if http_resp.status_code >= 400 else _parse_success(http_resp, req.model, latency_ms)
