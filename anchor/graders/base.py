"""Grader protocol. See ARCHITECTURE.md §5.3.

Graders are pure w.r.t. their inputs and must be deterministic given
`(case, resp)` — except judges, which is why judges get cached and pinned
separately (§6.3). Bump `version` on any behavior change so old runs stay
interpretable even after a grader's logic evolves.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from anchor.core.models import Case, Response, Verdict
from anchor.core.judge_cache import JudgeCache
from anchor.providers.base import Provider


@dataclass
class GraderContext:
    """Passed to every `grade()` call. Empty for the pure graders shipped in
    P1 (exact/contains/regex) — judge graders (§6.3, landing in P3) will hang
    their pinned judge provider/model and cache handle off this additively,
    without changing the Grader protocol shape.
    """
    judge_provider: Provider | None = None
    judge_model: str | None = None
    judge_cache: JudgeCache | None = None
    baseline_responses: dict[tuple[str, int], Response] = field(default_factory=dict)
    repeat: int = 0


class Grader(Protocol):
    kind: str
    version: str

    async def grade(self, case: Case, resp: Response, ctx: GraderContext) -> Verdict: ...
