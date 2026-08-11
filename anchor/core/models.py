"""Pydantic data model. See ARCHITECTURE.md §4.

`id` fields are user-facing strings; `*_hash` fields are sha256, first 16 hex chars
(see `anchor.core.suite`). Nothing here talks to a provider or the filesystem —
this module is pure schema.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class GraderSpec(BaseModel):
    kind: str
    required: bool = True
    weight: float = 1.0
    config: dict[str, Any] = Field(default_factory=dict)


class Case(BaseModel):
    """A single, frozen test case. Never auto-renumber `id` — it is the stable key
    that ties results across runs months apart.
    """

    id: str
    input: str | list[Message]
    system: str | None = None
    expect: Any = None
    graders: list[GraderSpec] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    weight: float = 1.0


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class Usage(BaseModel):
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0
    reasoning: int = 0


class ErrorInfo(BaseModel):
    type: str
    message: str
    retryable: bool = False
    status_code: int | None = None
    retry_after: float | None = None


class Request(BaseModel):
    """Provider-boundary input. Adapters normalize to/from this; they never grade,
    never retry-policy-decide (that's providers/base.py), never print.
    """

    model: str
    messages: list[Message]
    system: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class Response(BaseModel):
    """Provider-boundary output. On terminal failure a provider returns a Response
    with `error` set — it never raises into the runner (§5.1).
    """

    text: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    finish_reason: str = ""
    usage: Usage = Field(default_factory=Usage)
    latency_ms: int = 0
    model_resolved: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)
    error: ErrorInfo | None = None


class Verdict(BaseModel):
    grader: str
    score: float
    passed: bool
    rationale: str = ""
    cost_usd: float = 0.0
    error: str | None = None


class Result(BaseModel):
    """One row of results.jsonl."""

    case_id: str
    case_hash: str
    repeat: int = 0
    response: Response | None = None
    verdicts: list[Verdict] = Field(default_factory=list)
    score: float = 0.0
    passed: bool = False
    cost_usd: float = 0.0
    cached: bool = False
    status: Literal["ok", "provider_error", "grader_error", "skipped"] = "ok"


class Totals(BaseModel):
    score: float = 0.0
    pass_rate: float = 0.0
    cost_usd: float = 0.0
    p50_latency: float = 0.0
    p95_latency: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0


class EnvInfo(BaseModel):
    python: str
    os: str


class GitInfo(BaseModel):
    commit: str | None = None
    dirty: bool = False


class RunManifest(BaseModel):
    """manifest.json — everything needed to reproduce or invalidate a run."""

    run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    anchor_version: str

    suite_hash: str
    case_count: int
    case_hashes: dict[str, str] = Field(default_factory=dict)

    provider: str
    model: str
    model_resolved: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    repeats: int = 1
    seed: int | None = None

    grader_versions: dict[str, str] = Field(default_factory=dict)
    judge_model: str | None = None
    judge_prompt_hash: str | None = None

    totals: Totals = Field(default_factory=Totals)
    env: EnvInfo
    git: GitInfo | None = None

    notes: str = ""
    tags: list[str] = Field(default_factory=list)
