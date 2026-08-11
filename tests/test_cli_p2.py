"""End-to-end CLI coverage for P2: cache flags, bless, and compare — all
against httpx.MockTransport, zero live network calls (§11).
"""
from __future__ import annotations

import json as jsonlib

import httpx
import pytest
from typer.testing import CliRunner

from anchor.cli.main import app
from anchor.providers.anthropic import AnthropicProvider

runner = CliRunner()


def _handler(answer_map: dict[str, str]):
    def handler(request):
        body = jsonlib.loads(request.content)
        user_text = body["messages"][-1]["content"]
        text = next((v for k, v in answer_map.items() if k in user_text), "")
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": text}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 5, "output_tokens": 1},
                "model": "claude-opus-5",
            },
        )

    return handler


def _provider_factory(answer_map: dict[str, str]):
    def factory(kind, api_key_env=None, base_url=None):
        return AnthropicProvider(client=httpx.AsyncClient(transport=httpx.MockTransport(_handler(answer_map))))

    return factory


@pytest.fixture(autouse=True)
def isolated_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    runner.invoke(app, ["init", "."])


def test_run_cache_hit_avoids_second_provider_call(monkeypatch):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "4"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    def factory(kind, api_key_env=None, base_url=None):
        return AnthropicProvider(client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    monkeypatch.setattr("anchor.cli.run.build_provider", factory)

    assert runner.invoke(app, ["run"]).exit_code == 0
    assert runner.invoke(app, ["run"]).exit_code == 0
    assert calls["n"] == 1, "second run should be a cache hit"

    assert runner.invoke(app, ["run", "--refresh"]).exit_code == 0
    assert calls["n"] == 2, "--refresh should skip the cache read"

    assert runner.invoke(app, ["run", "--no-cache"]).exit_code == 0
    assert calls["n"] == 3, "--no-cache should never read or write the cache"


def test_bless_and_show_baseline(monkeypatch):
    monkeypatch.setattr("anchor.cli.run.build_provider", _provider_factory({"2": "4"}))
    assert runner.invoke(app, ["run"]).exit_code == 0

    bless = runner.invoke(app, ["runs", "bless", "@latest", "prod"])
    assert bless.exit_code == 0

    show = runner.invoke(app, ["runs", "show", "@baseline:prod"])
    assert show.exit_code == 0


def test_compare_exits_2_on_regression_and_only_filters(monkeypatch):
    with open("cases/example.jsonl", "a", encoding="utf-8") as f:
        f.write(
            '{"id": "example-2", "input": "capital of Italy? one word.", '
            '"expect": "Rome", "tags": ["geo"]}\n'
        )

    # --no-cache on both: runs A and B send the identical request for
    # example-2 (same messages/params), and the whole point here is to
    # simulate two different model versions answering it differently — a
    # cache hit on run A's answer would silently erase that difference.
    monkeypatch.setattr("anchor.cli.run.build_provider", _provider_factory({"2": "4", "capital": "Rome"}))
    assert runner.invoke(app, ["run", "--name", "a", "--no-cache"]).exit_code == 0

    monkeypatch.setattr(
        "anchor.cli.run.build_provider", _provider_factory({"2": "4", "capital": "not rome"})
    )
    assert runner.invoke(app, ["run", "--name", "b", "--no-cache"]).exit_code == 0

    result = runner.invoke(app, ["compare", "--", "-2", "-1"])
    assert result.exit_code == 2
    assert "REGRESSION" in result.output

    only = runner.invoke(app, ["compare", "--only", "regression", "--", "-2", "-1"])
    assert only.exit_code == 2
    assert "example-2" in only.output
    assert "example-1" not in only.output

    as_json = runner.invoke(app, ["compare", "--format", "json", "--", "-2", "-1"])
    assert as_json.exit_code == 2
    payload = jsonlib.loads(as_json.output)
    assert payload["counts"]["REGRESSION"] == 1
