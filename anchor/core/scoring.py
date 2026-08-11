"""Aggregate verdicts -> case/suite scores. See ARCHITECTURE.md §7.1.

```
case_score   = weighted mean of verdict scores   (combine: mean | min | all — default mean)
case_passed  = all(required verdicts passed)
case_final   = mean over repeats                 (also keep stdev)
suite_score  = weight-normalized mean over cases
pass_rate    = mean(case_passed) over case×repeat
```
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np

from anchor.core.models import Case, GraderSpec, Result, Totals, Verdict

Combine = str  # "mean" | "min" | "all"


def combine_verdicts(verdicts: list[Verdict], specs: list[GraderSpec], combine: Combine = "mean") -> float:
    """Combine one case-repeat's per-grader verdicts into a single score."""
    if not verdicts:
        return 0.0
    aligned = specs if specs and len(specs) == len(verdicts) else []
    weights = [s.weight for s in aligned] if aligned else [1.0] * len(verdicts)

    if combine == "mean":
        total_weight = sum(weights) or 1.0
        return sum(v.score * w for v, w in zip(verdicts, weights)) / total_weight
    if combine == "min":
        return min(v.score for v in verdicts)
    if combine == "all":
        return 1.0 if all(v.passed for v in verdicts) else 0.0
    raise ValueError(f"unknown combine mode {combine!r}; expected mean|min|all")


def case_passed(verdicts: list[Verdict], specs: list[GraderSpec]) -> bool:
    """A case-repeat passes iff every *required* grader passed. `specs` must be
    aligned 1:1 with `verdicts` (the runner builds them together); if that
    invariant doesn't hold, every verdict is treated as required."""
    aligned = specs if specs and len(specs) == len(verdicts) else []
    if aligned:
        return all(v.passed for v, s in zip(verdicts, aligned) if s.required)
    return all(v.passed for v in verdicts)


def repeat_stats(scores: list[float]) -> tuple[float, float]:
    """(mean, stdev) of one case's score across its repeats."""
    if not scores:
        return 0.0, 0.0
    arr = np.asarray(scores, dtype=float)
    return float(arr.mean()), float(arr.std())


def collapse_by_case(results: list[Result]) -> dict[str, float]:
    """case_final: mean score over repeats, keyed by case_id."""
    grouped: dict[str, list[float]] = defaultdict(list)
    for r in results:
        grouped[r.case_id].append(r.score)
    return {case_id: repeat_stats(scores)[0] for case_id, scores in grouped.items()}


def suite_score(case_scores: dict[str, float], weights: dict[str, float]) -> float:
    """Weight-normalized mean over cases. `weights` missing a case_id defaults
    that case's weight to 1.0."""
    if not case_scores:
        return 0.0
    total_weight = sum(weights.get(cid, 1.0) for cid in case_scores) or 1.0
    return sum(case_scores[cid] * weights.get(cid, 1.0) for cid in case_scores) / total_weight


def pass_rate(results: list[Result]) -> float:
    """mean(case_passed) over case×repeat."""
    if not results:
        return 0.0
    return sum(1 for r in results if r.passed) / len(results)


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    return float(np.percentile(np.asarray(sorted_values, dtype=float), pct))


def aggregate_totals(results: list[Result]) -> Totals:
    """Roll a run's Results up into `RunManifest.totals`."""
    if not results:
        return Totals()

    scores = [r.score for r in results]
    latencies = sorted(r.response.latency_ms for r in results if r.response is not None)
    tokens_in = sum(r.response.usage.input for r in results if r.response is not None)
    tokens_out = sum(r.response.usage.output for r in results if r.response is not None)
    cost = sum(r.cost_usd for r in results)

    return Totals(
        score=float(np.mean(scores)),
        pass_rate=pass_rate(results),
        cost_usd=cost,
        p50_latency=_percentile(latencies, 50),
        p95_latency=_percentile(latencies, 95),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
    )


def by_tag(cases: dict[str, Case], results: list[Result]) -> dict[str, dict[str, float]]:
    """Per-tag breakdown: {tag: {"score", "pass_rate"}}. Per §7.1, this is the
    insight users actually act on — "worse at extraction, better at
    summarization" — so it's not an afterthought bolted onto the report.
    """
    grouped: dict[str, list[Result]] = defaultdict(list)
    for r in results:
        case = cases.get(r.case_id)
        if case is None:
            continue
        for tag in case.tags:
            grouped[tag].append(r)

    return {
        tag: {"score": float(np.mean([r.score for r in rs])), "pass_rate": pass_rate(rs)}
        for tag, rs in grouped.items()
    }
