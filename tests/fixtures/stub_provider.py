"""A deterministic, network-free provider for tests and the examples/ CI run
(§11: "examples/ suite runs in CI against a stub provider"). Not registered in
anchor.providers.registry — never selectable by end users, test-only double.
"""
from __future__ import annotations

from anchor.core.models import Request, Response, Usage
from anchor.providers.base import BaseProvider


class StubProvider(BaseProvider):
    """Looks up the last user message in `responses` and echoes back the
    match, or `default` if there isn't one. Instant, no I/O, no retries."""

    name = "stub"
    version = "1"

    def __init__(self, responses: dict[str, str] | None = None, default: str = ""):
        self.responses = responses or {}
        self.default = default

    def supports(self, feature: str) -> bool:
        return False

    async def _call(self, req: Request) -> Response:
        user_text = req.messages[-1].content if req.messages else ""
        text = self.responses.get(user_text, self.default)
        return Response(
            text=text,
            finish_reason="stop",
            usage=Usage(input=len(user_text.split()), output=len(text.split())),
            latency_ms=1,
            model_resolved=req.model,
        )
