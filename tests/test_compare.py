"""Compare engine (§7.2): the full classification table, aggregation, display
ordering, and per-tag breakdown.
"""
from __future__ import annotations

import pytest

from anchor.core.compare import (
    CaseDiff,
    Classification,
    classify_case,
    compare_runs,
    sort_diffs_for_display,
    tag_breakdown,
)
from anchor.core.models import EnvInfo, Result, RunManifest, Totals


def _result(case_id, score, passed, case_hash="h", status="ok"):
    return Result(case_id=case_id, case_hash=case_hash, repeat=0, score=score, passed=passed, status=status)


def _manifest(run_id, score=0.0, cost=0.0, p95=0.0):
    return RunManifest(
        run_id=run_id,
        anchor_version="0.1.0",
        suite_hash="s",
        case_count=1,
        provider="anthropic",
        model="m",
        totals=Totals(score=score, cost_usd=cost, p95_latency=p95),
        env=EnvInfo(python="3.x", os="test"),
    )


@pytest.mark.parametrize(
    "score_a,passed_a,score_b,passed_b,expected",
    [
        (1.0, True, 0.0, False, Classification.REGRESSION),
        (0.0, False, 1.0, True, Classification.FIX),
        (0.5, True, 0.9, True, Classification.DRIFT),
        (0.8, True, 0.82, True, Classification.STABLE),
        (0.2, False, 0.1, False, Classification.STABLE),  # both fail, small delta
        (0.9, False, 0.1, False, Classification.DRIFT),  # both fail, big delta
    ],
)
def test_classification_matrix(score_a, passed_a, score_b, passed_b, expected):
    diff = classify_case(
        "c", [_result("c", score_a, passed_a)], [_result("c", score_b, passed_b)], threshold=0.15
    )
    assert diff.classification == expected


def test_error_when_either_side_has_a_non_ok_status():
    diff = classify_case(
        "c", [_result("c", 1.0, True)], [_result("c", 0.0, False, status="provider_error")], 0.15
    )
    assert diff.classification == Classification.ERROR


def test_changed_when_case_hash_differs():
    diff = classify_case(
        "c", [_result("c", 1.0, True, case_hash="h1")], [_result("c", 1.0, True, case_hash="h2")], 0.15
    )
    assert diff.classification == Classification.CHANGED
    assert "case_hash differs" in diff.note


def test_missing_when_present_in_only_one_run():
    assert classify_case("c", [_result("c", 1.0, True)], [], 0.15).classification == Classification.MISSING
    assert classify_case("c", [], [_result("c", 1.0, True)], 0.15).classification == Classification.MISSING


def test_case_passed_requires_every_repeat_to_pass():
    results_a = [_result("c", 1.0, True), _result("c", 1.0, True)]
    results_b = [_result("c", 1.0, True), _result("c", 0.0, False)]  # one repeat regressed
    assert classify_case("c", results_a, results_b, 0.15).classification == Classification.REGRESSION


def test_compare_runs_aggregates_counts_and_manifest_deltas():
    results_a = [_result("c1", 1.0, True), _result("c2", 0.0, False)]
    results_b = [_result("c1", 0.0, False), _result("c2", 1.0, True)]
    manifest_a = _manifest("a", score=0.5, cost=1.0, p95=100)
    manifest_b = _manifest("b", score=0.5, cost=1.5, p95=150)

    report = compare_runs(manifest_a, results_a, manifest_b, results_b, threshold=0.15)

    assert report.counts["REGRESSION"] == 1
    assert report.counts["FIX"] == 1
    assert report.delta_cost_usd == pytest.approx(0.5)
    assert report.delta_p95_latency == pytest.approx(50)


def test_sort_diffs_regression_always_first_then_error_fix_drift():
    diffs = [
        CaseDiff("a", Classification.STABLE),
        CaseDiff("b", Classification.REGRESSION),
        CaseDiff("c", Classification.FIX),
        CaseDiff("d", Classification.ERROR),
        CaseDiff("e", Classification.DRIFT),
    ]
    ordered = sort_diffs_for_display(diffs)
    assert [d.classification for d in ordered] == [
        Classification.REGRESSION,
        Classification.ERROR,
        Classification.FIX,
        Classification.DRIFT,
        Classification.STABLE,
    ]


def test_tag_breakdown_attributes_regression_to_its_own_tag_only():
    diffs = [
        CaseDiff("c1", Classification.REGRESSION, 1.0, 0.0, -1.0),
        CaseDiff("c2", Classification.STABLE, 1.0, 1.0, 0.0),
    ]
    case_tags = {"c1": ["math"], "c2": ["geo"]}
    breakdown = tag_breakdown(diffs, case_tags)
    assert breakdown["math"]["regressions"] == 1
    assert breakdown["geo"]["regressions"] == 0
    assert breakdown["math"]["mean_delta"] == pytest.approx(-1.0)
