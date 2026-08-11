"""Async run execution. See ARCHITECTURE.md §6.1.

```
load suite -> validate -> expand (case × repeats) -> asyncio.Semaphore(concurrency)
  -> cache lookup -> provider.generate -> graders (parallel per case) -> stream Result to jsonl
```

Adaptive concurrency backoff on sustained 429s is a seam left for later — the
semaphore's width is fixed for the life of a run. Retries already live in the
provider layer (`providers/base.py`), so this module never re-implements backoff.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from anchor.core.cache import ResponseCache, cache_key
from anchor.core.models import Case, GraderSpec, Message, Request, Result, Verdict
from anchor.core.scoring import case_passed, combine_verdicts
from anchor.core.suite import case_hash
from anchor.graders.base import GraderContext
from anchor.graders.registry import build_grader
from anchor.providers.base import Provider


@dataclass
class RunConfig:
    model: str
    default_graders: list[GraderSpec] = field(default_factory=list)
    params: dict = field(default_factory=dict)
    repeats: int = 1
    concurrency: int = 8
    combine: str = "mean"  # mean | min | all, per §7.1
    cache: ResponseCache | None = None  # None = --no-cache: never read, never write
    refresh: bool = False  # True = --refresh: skip the read, still write


def _resolve_messages(case: Case) -> tuple[list[Message], str | None]:
    if isinstance(case.input, str):
        return [Message(role="user", content=case.input)], case.system
    return list(case.input), case.system


def _existing_keys(results_path: Path) -> set[tuple[str, int]]:
    """(case_id, repeat) pairs already recorded in results.jsonl, for --resume."""
    if not results_path.exists():
        return set()
    keys: set[tuple[str, int]] = set()
    for line in results_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        data = json.loads(line)
        keys.add((data["case_id"], data["repeat"]))
    return keys


async def _run_one(
    case: Case,
    repeat: int,
    hash_: str,
    provider: Provider,
    config: RunConfig,
    ctx: GraderContext,
) -> Result:
    messages, system = _resolve_messages(case)
    params = {**config.params, **case.params}
    req = Request(model=config.model, messages=messages, system=system, params=params)

    key = None
    if config.cache is not None:
        key = cache_key(provider.name, provider.version, config.model, params, messages, system, repeat)

    resp = None
    cached = False
    if key is not None and not config.refresh:
        resp = config.cache.get(key)
        cached = resp is not None

    if resp is None:
        resp = await provider.generate(req)
        if key is not None and resp.error is None:
            # Only cache successful responses — a transient outage shouldn't
            # get baked in as a permanent "answer" for this key.
            config.cache.put(key, resp)

    if resp.error is not None:
        # Never score an outage as a quality regression (§5.1): 0 score, but a
        # distinct status so compare/report can call it out separately.
        return Result(
            case_id=case.id,
            case_hash=hash_,
            repeat=repeat,
            response=resp,
            score=0.0,
            passed=False,
            cost_usd=0.0,
            cached=cached,
            status="provider_error",
        )

    specs = case.graders or config.default_graders
    try:
        graders = [build_grader(spec) for spec in specs]
        verdicts: list[Verdict] = list(
            await asyncio.gather(*(g.grade(case, resp, ctx) for g in graders))
        )
    except Exception as exc:
        return Result(
            case_id=case.id,
            case_hash=hash_,
            repeat=repeat,
            response=resp,
            score=0.0,
            passed=False,
            cost_usd=0.0,
            cached=cached,
            status="grader_error",
            verdicts=[Verdict(grader="_runner", score=0.0, passed=False, error=str(exc))],
        )

    return Result(
        case_id=case.id,
        case_hash=hash_,
        repeat=repeat,
        response=resp,
        verdicts=verdicts,
        score=combine_verdicts(verdicts, specs, config.combine),
        passed=case_passed(verdicts, specs),
        cost_usd=sum(v.cost_usd for v in verdicts),
        cached=cached,
        status="ok",
    )


async def run_suite(
    cases: list[Case],
    provider: Provider,
    config: RunConfig,
    results_path: Path,
    resume: bool = False,
    on_result: Callable[[Result], None] | None = None,
) -> list[Result]:
    """Execute `cases` × `config.repeats` under a concurrency semaphore,
    streaming each `Result` to `results_path` (JSONL, append mode) as soon as
    it completes — a killed run is resumable by rerunning with `resume=True`,
    which skips any `(case_id, repeat)` pair already on disk.

    File order is arrival order, not suite order (§6.1) — readers should sort
    by `(case_id, repeat)` themselves.
    """
    hashes = {c.id: case_hash(c) for c in cases}
    skip = _existing_keys(results_path) if resume else set()

    jobs = [
        (case, repeat)
        for case in cases
        for repeat in range(config.repeats)
        if (case.id, repeat) not in skip
    ]

    results_path.parent.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(config.concurrency)
    write_lock = asyncio.Lock()
    ctx = GraderContext()
    results: list[Result] = []

    async def worker(case: Case, repeat: int) -> None:
        async with semaphore:
            result = await _run_one(case, repeat, hashes[case.id], provider, config, ctx)
        async with write_lock:
            with results_path.open("a", encoding="utf-8") as f:
                f.write(result.model_dump_json() + "\n")
        results.append(result)
        if on_result is not None:
            on_result(result)

    if jobs:
        await asyncio.gather(*(worker(case, repeat) for case, repeat in jobs))

    return results
