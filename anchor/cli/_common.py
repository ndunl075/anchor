"""Shared run-ref resolution and manifest/result loading, used by both
`anchor run`/`runs` and `anchor compare` (§8).

Run refs: `run_id`, `@latest`, `@baseline`, `@baseline:<name>`, `-N` (Nth most
recent, 1-indexed — `-1` is the same run `@latest` would give you).
"""
from __future__ import annotations

import re
from pathlib import Path

import typer

from anchor.core.models import Result, RunManifest

RUNS_DIR = Path(".anchor/runs")
BASELINES_DIR = Path(".anchor/baselines")

_NTH_MOST_RECENT = re.compile(r"^-(\d+)$")


def _manifest_paths() -> list[Path]:
    return list(RUNS_DIR.glob("*/manifest.json"))


def _nth_most_recent(n: int) -> str:
    paths = _manifest_paths()
    if not paths:
        raise typer.BadParameter("no runs exist yet — try `anchor run`")
    # Sort by the manifest's own created_at, not mtime — mtime can lie across
    # filesystem copies/checkouts, created_at is what the run actually claims.
    manifests = sorted(
        (RunManifest.model_validate_json(p.read_text(encoding="utf-8")) for p in paths),
        key=lambda m: m.created_at,
        reverse=True,
    )
    if n < 1 or n > len(manifests):
        raise typer.BadParameter(f"only {len(manifests)} run(s) exist; can't resolve the {n}th most recent")
    return manifests[n - 1].run_id


def resolve_run_ref(ref: str) -> str:
    if ref == "@latest":
        return _nth_most_recent(1)

    match = _NTH_MOST_RECENT.match(ref)
    if match:
        return _nth_most_recent(int(match.group(1)))

    if ref == "@baseline" or ref.startswith("@baseline:"):
        name = ref.partition(":")[2] or "default"
        pointer = BASELINES_DIR / name
        if not pointer.exists():
            raise typer.BadParameter(
                f"no baseline named {name!r} — bless one with `anchor runs bless <run> {name}`"
            )
        return pointer.read_text(encoding="utf-8").strip()

    return ref


def load_manifest(run_id: str) -> RunManifest:
    path = RUNS_DIR / run_id / "manifest.json"
    if not path.exists():
        raise typer.BadParameter(f"no run {run_id!r} in {RUNS_DIR}")
    return RunManifest.model_validate_json(path.read_text(encoding="utf-8"))


def load_results(run_id: str) -> list[Result]:
    path = RUNS_DIR / run_id / "results.jsonl"
    if not path.exists():
        return []
    return [
        Result.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
