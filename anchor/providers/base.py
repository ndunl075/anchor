"""Provider protocol + shared retry/backoff. See ARCHITECTURE.md §5.1.

Adapters (anthropic.py, openai.py, ...) implement `_call` — one HTTP round trip,
normalized to `Response`. They never decide retry policy and never raise into the
runner: `BaseProvider.generate()` owns backoff and always returns a `Response`,
setting `.error` on terminal failure.
"""
from __future__ import annotations

import asyncio
import os
import random
import time
from typing import Protocol

from anchor.core.models import ErrorInfo, Request, Response

# Status codes worth retrying: rate limits and transient server-side failures.
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class Provider(Protocol):
    name: str
    version: str

    async def generate(self, req: Request) -> Response: ...

    def supports(self, feature: str) -> bool: ...
    # feature in {"tools", "system", "json_mode", "cache"}


class MissingAPIKeyError(RuntimeError):
    pass


def parse_retry_after(header: str | None) -> float | None:
    """Parse a `Retry-After` header value (seconds, as all providers we target
    send it) into a float, or None if absent/unparseable."""
    if not header:
        return None
    try:
        return float(header)
    except ValueError:
        return None


def read_api_key(env_var: str) -> str:
    key = os.environ.get(env_var)
    if not key:
        raise MissingAPIKeyError(
            f"{env_var} is not set. Secrets come from the environment only — "
            f"never from anchor.yaml or run records (see ARCHITECTURE.md §2)."
        )
    return key


class BaseProvider:
    """Owns the retry loop so concrete adapters stay dumb HTTP mappers.

    Retries: exponential backoff + jitter on retryable errors, `max_retries=3`,
    honoring `Retry-After` when the adapter surfaces one. Retries do not count as
    `repeat`s and do not multiply cost accounting — `generate()` always returns
    exactly one `Response` per call.
    """

    name: str = "base"
    version: str = "0"
    max_retries: int = 3
    base_delay: float = 1.0

    def supports(self, feature: str) -> bool:
        return False

    async def _call(self, req: Request) -> Response:
        raise NotImplementedError

    async def generate(self, req: Request) -> Response:
        attempt = 0
        while True:
            start = time.monotonic()
            try:
                resp = await self._call(req)
            except Exception as exc:  # transport failure: timeout, DNS, TLS, ...
                resp = Response(
                    latency_ms=int((time.monotonic() - start) * 1000),
                    error=ErrorInfo(
                        type=type(exc).__name__,
                        message=str(exc),
                        retryable=True,
                    ),
                )

            if resp.error is None or not resp.error.retryable or attempt >= self.max_retries:
                return resp

            attempt += 1
            await asyncio.sleep(self._retry_delay(attempt, resp.error))

    def _retry_delay(self, attempt: int, error: ErrorInfo) -> float:
        if error.retry_after is not None:
            return max(0.0, error.retry_after)
        jitter = random.uniform(0, 0.5)
        return self.base_delay * (2 ** (attempt - 1)) + jitter
