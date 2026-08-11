"""Aggregation per §7.1: combine strategies, required-only case_passed, and
suite/tag rollups.
"""
from __future__ import annotations

import pytest

from anchor.core.models import GraderSpec, Result, Response, Usage, Verdict
from anchor.core.scoring import (
    aggregate_totals,
    case_passed,
    collapse_by_case,
    combine_verdicts,
    pass_rate,
    suite_score,
)


def _verdict(score, passed):
    return Verdict(grader="g", score=score, passed=passed)


def test_combine_mean_is_weighted():
    verdicts = [_verdict(1.0, True), _verdict(0.0, False)]
    specs = [GraderSpec(kind="a", weight=3.0), GraderSpec(kind="b", weight=1.0)]
    assert combine_verdicts(verdicts, specs, "mean") == pytest.approx(0.75)


def test_combine_min_and_all():
    verdicts = [_verdict(1.0, True), _verdict(0.4, True)]
    assert combine_verdicts(verdicts, [], "min") == pytest.approx(0.4)
    assert combine_verdicts(verdicts, [], "all") == 1.0

    verdicts_with_fail = [_verdict(1.0, True), _verdict(0.4, False)]
    assert combine_verdicts(verdicts_with_fail, [], "all") == 0.0


def test_combine_unknown_mode_raises():
    with pytest.raises(ValueError):
        combine_verdicts([_verdict(1.0, True)], [], "median")


def test_case_passed_only_considers_required_graders():
    verdicts = [_verdict(1.0, True), _verdict(0.0, False)]
    specs = [GraderSpec(kind="a", required=True), GraderSpec(kind="b", required=False)]
    assert case_passed(verdicts, specs) is True  # the failing grader is optional


def test_collapse_by_case_averages_repeats():
    results = [
        Result(case_id="c1", case_hash="h", repeat=0, score=1.0, passed=True),
        Result(case_id="c1", case_hash="h", repeat=1, score=0.5, passed=True),
    ]
    assert collapse_by_case(results) == {"c1": pytest.approx(0.75)}


def test_suite_score_is_weight_normalized():
    scores = {"c1": 1.0, "c2": 0.0}
    weights = {"c1": 3.0, "c2": 1.0}
    assert suite_score(scores, weights) == pytest.approx(0.75)


def test_pass_rate_over_case_x_repeat():
    results = [
        Result(case_id="c1", case_hash="h", repeat=0, score=1.0, passed=True),
        Result(case_id="c1", case_hash="h", repeat=1, score=0.0, passed=False),
    ]
    assert pass_rate(results) == pytest.approx(0.5)


def test_aggregate_totals_percentiles_and_tokens():
    results = [
        Result(
            case_id="c1", case_hash="h", repeat=0, score=1.0, passed=True,
            response=Response(latency_ms=100, usage=Usage(input=10, output=5)),
        ),
        Result(
            case_id="c2", case_hash="h", repeat=0, score=0.0, passed=False,
            response=Response(latency_ms=200, usage=Usage(input=8, output=3)),
        ),
    ]
    totals = aggregate_totals(results)
    assert totals.tokens_in == 18
    assert totals.tokens_out == 8
    assert totals.pass_rate == pytest.approx(0.5)


def test_aggregate_totals_empty_is_zeroed():
    totals = aggregate_totals([])
    assert totals.score == 0.0
    assert totals.pass_rate == 0.0
