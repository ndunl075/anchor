"""run_suite (§6.1): concurrency, scoring, provider/grader error handling,
JSONL streaming, and --resume semantics.
"""
from __future__ import annotations

import asyncio

import pytest

from anchor.core.models import Case, ErrorInfo, GraderSpec, Request, Response, Usage
from anchor.core.runner import RunConfig, run_suite
from anchor.providers.base import BaseProvider


class FakeProvider(BaseProvider):
    name = "fake"
    version = "1"

    def __init__(self, answer: str = "4"):
        self.answer = answer

    def supports(self, feature: str) -> bool:
        return False

    async def _call(self, req: Request) -> Response:
        return Response(text=self.answer, usage=Usage(input=1, output=1), model_resolved=req.model)


class ErrorProvider(BaseProvider):
    name = "error"
    version = "1"

    def supports(self, feature: str) -> bool:
        return False

    async def _call(self, req: Request) -> Response:
        return Response(error=ErrorInfo(type="boom", message="down", retryable=False))


async def test_run_suite_scores_and_streams_results(tmp_path):
    cases = [
        Case(id="c1", input="add 2+2", expect="4", graders=[GraderSpec(kind="exact")]),
        Case(id="c2", input="what color", expect="red", graders=[GraderSpec(kind="exact")]),
    ]
    results_path = tmp_path / "results.jsonl"
    config = RunConfig(model="fake-model", repeats=2, concurrency=4)

    results = await run_suite(cases, FakeProvider(), config, results_path)

    assert len(results) == 4
    by_case = {(r.case_id, r.repeat): r for r in results}
    assert by_case[("c1", 0)].passed and by_case[("c1", 1)].passed
    assert not by_case[("c2", 0)].passed
    assert len(results_path.read_text(encoding="utf-8").splitlines()) == 4


async def test_run_suite_marks_provider_errors_without_scoring_them_as_regressions(tmp_path):
    cases = [Case(id="c1", input="x", expect="4", graders=[GraderSpec(kind="exact")])]
    results = await run_suite(cases, ErrorProvider(), RunConfig(model="m"), tmp_path / "results.jsonl")
    assert results[0].status == "provider_error"
    assert results[0].score == 0.0
    assert results[0].passed is False


async def test_run_suite_handles_grader_error_without_crashing(tmp_path):
    cases = [Case(id="c1", input="x", expect="4", graders=[GraderSpec(kind="regex", config={})])]
    results = await run_suite(cases, FakeProvider(), RunConfig(model="m"), tmp_path / "results.jsonl")
    assert results[0].status == "grader_error"
    assert results[0].score == 0.0


async def test_resume_skips_completed_case_repeat_pairs(tmp_path):
    cases = [Case(id="c1", input="x", expect="4", graders=[GraderSpec(kind="exact")])]
    results_path = tmp_path / "results.jsonl"
    config = RunConfig(model="m", repeats=2)

    first = await run_suite(cases, FakeProvider(), config, results_path)
    assert len(first) == 2

    second = await run_suite(cases, FakeProvider(), config, results_path, resume=True)
    assert second == []
    assert len(results_path.read_text(encoding="utf-8").splitlines()) == 2


async def test_concurrency_semaphore_caps_in_flight_calls(tmp_path):
    in_flight = 0
    max_in_flight = 0
    lock = asyncio.Lock()

    class TrackingProvider(BaseProvider):
        name = "tracking"
        version = "1"

        def supports(self, feature: str) -> bool:
            return False

        async def _call(self, req: Request) -> Response:
            nonlocal in_flight, max_in_flight
            async with lock:
                in_flight += 1
                max_in_flight = max(max_in_flight, in_flight)
            await asyncio.sleep(0.01)
            async with lock:
                in_flight -= 1
            return Response(text="ok")

    cases = [Case(id=f"c{i}", input="x") for i in range(10)]
    config = RunConfig(model="m", concurrency=2)
    await run_suite(cases, TrackingProvider(), config, tmp_path / "results.jsonl")

    assert max_in_flight <= 2
