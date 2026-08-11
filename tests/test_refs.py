"""Run-ref resolution + bless round-trip (§8): run_id, @latest, @baseline[:name], -N."""
from __future__ import annotations

import pytest
import typer

from anchor.cli._common import BASELINES_DIR, RUNS_DIR, load_manifest, load_results, resolve_run_ref
from anchor.core.models import EnvInfo, RunManifest, Totals


@pytest.fixture(autouse=True)
def isolated_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def _write_manifest(run_id: str, created_at: str) -> None:
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest = RunManifest(
        run_id=run_id,
        created_at=created_at,
        anchor_version="0.1.0",
        suite_hash="h",
        case_count=1,
        provider="anthropic",
        model="claude-opus-5",
        totals=Totals(),
        env=EnvInfo(python="3.x", os="test"),
    )
    (run_dir / "manifest.json").write_text(manifest.model_dump_json(), encoding="utf-8")


def test_bare_run_id_passes_through():
    assert resolve_run_ref("some-run-id") == "some-run-id"


def test_at_latest_picks_most_recent_by_created_at():
    _write_manifest("r1", "2026-01-01T00:00:00Z")
    _write_manifest("r2", "2026-01-02T00:00:00Z")
    assert resolve_run_ref("@latest") == "r2"


def test_nth_most_recent():
    _write_manifest("r1", "2026-01-01T00:00:00Z")
    _write_manifest("r2", "2026-01-02T00:00:00Z")
    _write_manifest("r3", "2026-01-03T00:00:00Z")
    assert resolve_run_ref("-1") == "r3"
    assert resolve_run_ref("-2") == "r2"
    assert resolve_run_ref("-3") == "r1"


def test_at_latest_with_no_runs_raises():
    with pytest.raises(typer.BadParameter):
        resolve_run_ref("@latest")


def test_nth_out_of_range_raises():
    _write_manifest("r1", "2026-01-01T00:00:00Z")
    with pytest.raises(typer.BadParameter):
        resolve_run_ref("-2")


def test_unblessed_baseline_raises_with_bless_hint():
    with pytest.raises(typer.BadParameter, match="bless"):
        resolve_run_ref("@baseline")


def test_bless_round_trip():
    _write_manifest("r1", "2026-01-01T00:00:00Z")
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    (BASELINES_DIR / "prod").write_text("r1", encoding="utf-8")
    assert resolve_run_ref("@baseline:prod") == "r1"


def test_plain_at_baseline_uses_default_name():
    _write_manifest("r1", "2026-01-01T00:00:00Z")
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    (BASELINES_DIR / "default").write_text("r1", encoding="utf-8")
    assert resolve_run_ref("@baseline") == "r1"


def test_load_manifest_missing_run_raises():
    with pytest.raises(typer.BadParameter):
        load_manifest("nope")


def test_load_results_missing_file_returns_empty_list():
    _write_manifest("r1", "2026-01-01T00:00:00Z")
    assert load_results("r1") == []
