"""Paired diff and regression classification. See ARCHITECTURE.md §7.2.

Bootstrap CI (§7.4) lands in P4 — this module reports point-estimate deltas
only; the CLI headline says so explicitly rather than implying a precision
this doesn't have.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from anchor.core.models import Result, RunManifest
from anchor.core.stats import paired_bootstrap_ci


class Classification(str, Enum):
    REGRESSION = "REGRESSION"
    FIX = "FIX"
    DRIFT = "DRIFT"
    STABLE = "STABLE"
    ERROR = "ERROR"
    CHANGED = "CHANGED"
    MISSING = "MISSING"


# Output order: REGRESSION first, always. Then ERROR, FIX, DRIFT (§7.2).
_DISPLAY_ORDER = {
    Classification.REGRESSION: 0,
    Classification.ERROR: 1,
    Classification.FIX: 2,
    Classification.DRIFT: 3,
    Classification.STABLE: 4,
    Classification.CHANGED: 5,
    Classification.MISSING: 6,
}


@dataclass
class CaseDiff:
    case_id: str
    classification: Classification
    score_a: float | None = None
    score_b: float | None = None
    delta: float | None = None
    note: str = ""


@dataclass
class CompareReport:
    run_a: RunManifest
    run_b: RunManifest
    diffs: list[CaseDiff]
    counts: dict[str, int]
    delta_score: float
    delta_cost_usd: float
    delta_p95_latency: float
    delta_score_ci: tuple[float, float]
    significant: bool


def _group_by_case(results: list[Result]) -> dict[str, list[Result]]:
    grouped: dict[str, list[Result]] = {}
    for r in results:
        grouped.setdefault(r.case_id, []).append(r)
    return grouped


def _case_score(results: list[Result]) -> float:
    return sum(r.score for r in results) / len(results) if results else 0.0


def _case_passed(results: list[Result]) -> bool:
    """A case passes overall iff every one of its repeats passed — the same
    all(...) posture §7.1 uses for combining required verdicts."""
    return all(r.passed for r in results)


def classify_case(
    case_id: str, results_a: list[Result], results_b: list[Result], threshold: float
) -> CaseDiff:
    if not results_a or not results_b:
        return CaseDiff(case_id, Classification.MISSING, note="present in only one run")

    hash_a, hash_b = results_a[0].case_hash, results_b[0].case_hash
    if hash_a != hash_b:
        return CaseDiff(
            case_id, Classification.CHANGED, note=f"case_hash differs: {hash_a} vs {hash_b}"
        )

    if any(r.status != "ok" for r in results_a) or any(r.status != "ok" for r in results_b):
        statuses = sorted({r.status for r in results_a + results_b if r.status != "ok"})
        return CaseDiff(case_id, Classification.ERROR, note=f"status: {', '.join(statuses)}")

    score_a, score_b = _case_score(results_a), _case_score(results_b)
    passed_a, passed_b = _case_passed(results_a), _case_passed(results_b)
    delta = score_b - score_a

    if passed_a and not passed_b:
        classification = Classification.REGRESSION
    elif not passed_a and passed_b:
        classification = Classification.FIX
    elif abs(delta) > threshold:
        classification = Classification.DRIFT
    else:
        classification = Classification.STABLE

    return CaseDiff(case_id, classification, score_a, score_b, delta)


def compare_runs(
    manifest_a: RunManifest,
    results_a: list[Result],
    manifest_b: RunManifest,
    results_b: list[Result],
    threshold: float = 0.15,
) -> CompareReport:
    grouped_a, grouped_b = _group_by_case(results_a), _group_by_case(results_b)
    case_ids = sorted(set(grouped_a) | set(grouped_b))
    diffs = [
        classify_case(cid, grouped_a.get(cid, []), grouped_b.get(cid, []), threshold)
        for cid in case_ids
    ]

    counts = {c.value: 0 for c in Classification}
    for d in diffs:
        counts[d.classification.value] += 1

    paired_deltas = [d.delta for d in diffs if d.delta is not None and d.classification not in {Classification.ERROR, Classification.CHANGED, Classification.MISSING}]
    ci = paired_bootstrap_ci(paired_deltas)
    return CompareReport(
        run_a=manifest_a,
        run_b=manifest_b,
        diffs=diffs,
        counts=counts,
        delta_score=manifest_b.totals.score - manifest_a.totals.score,
        delta_cost_usd=manifest_b.totals.cost_usd - manifest_a.totals.cost_usd,
        delta_p95_latency=manifest_b.totals.p95_latency - manifest_a.totals.p95_latency,
        delta_score_ci=ci,
        significant=not (ci[0] <= 0 <= ci[1]),
    )


def sort_diffs_for_display(diffs: list[CaseDiff]) -> list[CaseDiff]:
    return sorted(diffs, key=lambda d: (_DISPLAY_ORDER[d.classification], d.case_id))


def tag_breakdown(diffs: list[CaseDiff], case_tags: dict[str, list[str]]) -> dict[str, dict]:
    """Per-tag regression/fix counts and mean Δscore — §7.1's "worse at
    extraction, better at summarization" insight, applied to a diff instead of
    a single run's score. `case_tags` comes from the *current* suite on disk;
    tags aren't part of case_hash, so this is best-effort if the suite changed
    tags since either run happened.
    """
    grouped: dict[str, list[CaseDiff]] = {}
    for diff in diffs:
        for tag in case_tags.get(diff.case_id, []):
            grouped.setdefault(tag, []).append(diff)

    breakdown: dict[str, dict] = {}
    for tag, tag_diffs in grouped.items():
        deltas = [d.delta for d in tag_diffs if d.delta is not None]
        breakdown[tag] = {
            "n": len(tag_diffs),
            "regressions": sum(1 for d in tag_diffs if d.classification == Classification.REGRESSION),
            "fixes": sum(1 for d in tag_diffs if d.classification == Classification.FIX),
            "mean_delta": (sum(deltas) / len(deltas)) if deltas else 0.0,
        }
    return breakdown
