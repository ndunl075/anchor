"""Runs the shipped examples/quickstart suite end to end against a stub
provider — §11's "examples/ suite runs in CI against a stub provider", with
zero live network calls.
"""
from __future__ import annotations

from pathlib import Path

from anchor.core.config import load_config
from anchor.core.runner import RunConfig, run_suite
from anchor.core.scoring import aggregate_totals, by_tag
from anchor.core.suite import load_suite

from tests.fixtures.stub_provider import StubProvider

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"

# Canned answers, keyed by the exact case input, that satisfy every grader in
# quickstart.jsonl — proves the pipeline (load -> run -> grade -> score ->
# aggregate) end to end without asserting anything about real model quality.
_ANSWERS = {
    "What is 12 * 12? Answer with just the number.": "144",
    "What is the capital of France? Answer with just the city name.": "Paris",
    "Name a primary color.": "Blue is one of the primary colors.",
    "List the first three planets from the sun, comma separated.": "Mercury, Venus, Earth",
    "Describe a cat without using the word 'dog'.": "A cat is a small, independent, furry pet.",
    "Give today's date in YYYY-MM-DD format only.": "2026-08-11",
    "Reply with exactly one word: yes or no. Is water wet?": "yes",
    "What is 2 + 2?": "4",
    "Summarize: 'The quick brown fox jumps over the lazy dog.' Mention the animal that jumps.": "The fox jumps.",
    "What color is the sky on a clear day? One word.": "Blue",
}


async def test_examples_suite_runs_end_to_end(tmp_path):
    config = load_config(EXAMPLES_DIR / "anchor.yaml")
    cases = load_suite(config.suite, EXAMPLES_DIR)
    assert len(cases) == 10

    provider = StubProvider(responses=_ANSWERS)
    run_config = RunConfig(model="stub-model", default_graders=config.graders, params=config.params)
    results = await run_suite(cases, provider, run_config, tmp_path / "results.jsonl")

    assert len(results) == 10
    assert all(r.status == "ok" for r in results)

    totals = aggregate_totals(results)
    assert totals.pass_rate == 1.0
    assert totals.score == 1.0

    tags = by_tag({c.id: c for c in cases}, results)
    assert set(tags) == {"math", "factual", "reasoning", "format"}
    assert all(v["pass_rate"] == 1.0 for v in tags.values())
