"""`anchor run` and `anchor runs` — execute a suite, list/inspect past runs (§8).

Run refs beyond a bare run_id or `@latest` (`@baseline[:name]`, `-N`) and the
`bless` command land with P2's replay/compare work (§10) — this is the P1
walking skeleton: run, and list/show what ran.
"""
from __future__ import annotations

import asyncio
import platform
import secrets
import subprocess
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from anchor import __version__
from anchor.core.config import ConfigError, load_config, resolve_provider_name
from anchor.core.models import EnvInfo, GitInfo, Result, RunManifest
from anchor.core.runner import RunConfig, run_suite
from anchor.core.scoring import aggregate_totals
from anchor.core.suite import SuiteError, compute_case_hashes, load_suite, suite_hash
from anchor.providers.registry import UnknownProviderError, build_provider
from anchor.report.terminal import make_progress, print_manifest_summary

console = Console()
RUNS_DIR = Path(".anchor/runs")

# If more than this fraction of results are provider_error, the run's exit
# code signals an operational failure (3) rather than success (0) — distinct
# from a usage/config error (1) and from `compare`'s regression code (2, §8).
_PROVIDER_ERROR_EXIT_THRESHOLD = 0.5


def _new_run_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3)


def _git_info(base_dir: Path) -> GitInfo | None:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=base_dir, capture_output=True, text=True, timeout=5
        )
        if commit.returncode != 0:
            return None
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=base_dir, capture_output=True, text=True, timeout=5
        )
        return GitInfo(commit=commit.stdout.strip(), dirty=bool(status.stdout.strip()))
    except (OSError, subprocess.SubprocessError):
        return None


def _load_all_results(results_path: Path) -> list[Result]:
    if not results_path.exists():
        return []
    return [
        Result.model_validate_json(line)
        for line in results_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def run(
    model: str = typer.Option("", "--model", help="Override the default model from anchor.yaml."),
    suite: str = typer.Option("", "--suite", help="Override the suite glob from anchor.yaml."),
    config_path: Path = typer.Option(Path("anchor.yaml"), "--config", "-c"),
    repeats: int = typer.Option(0, "--repeats", help="Override anchor.yaml's repeats (0 = use config)."),
    concurrency: int = typer.Option(0, "--concurrency", help="Override anchor.yaml's concurrency (0 = use config)."),
    tags: list[str] = typer.Option([], "--tags", help="Only run cases with any of these tags."),
    name: str = typer.Option("", "--name", help="Free-text note stored in the manifest."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Not yet implemented — cost estimate lands in P4 (§10)."),
    no_cache: bool = typer.Option(False, "--no-cache", help="Accepted for forward-compat; caching lands in P2 (§10)."),
    resume: str = typer.Option("", "--resume", help="Resume run_id, skipping completed (case_id, repeat) pairs."),
    baseline: bool = typer.Option(False, "--baseline", help="Not yet implemented — baseline-diff mode lands in P3 (§10)."),
) -> None:
    """Score a suite against a model."""
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        console.print(f"[red]error:[/] {exc}")
        raise typer.Exit(code=1)

    if dry_run or baseline:
        flag = "--dry-run" if dry_run else "--baseline"
        console.print(f"[yellow]{flag} isn't implemented yet — see ARCHITECTURE.md §10 for the phase it lands in.[/]")
        raise typer.Exit(code=1)

    target_model = model or config.model
    if not target_model:
        console.print("[red]error:[/] no model given: pass --model or set `model:` in anchor.yaml")
        raise typer.Exit(code=1)

    try:
        cases = load_suite(suite or config.suite, config_path.parent)
    except SuiteError as exc:
        console.print(f"[red]error:[/] {exc}")
        raise typer.Exit(code=1)

    if tags:
        cases = [c for c in cases if set(c.tags) & set(tags)]
    if not cases:
        console.print("[yellow]no cases matched — nothing to run[/]")
        raise typer.Exit(code=0)

    try:
        provider_name, bare_model = resolve_provider_name(target_model, config)
    except ConfigError as exc:
        console.print(f"[red]error:[/] {exc}")
        raise typer.Exit(code=1)

    provider_cfg = config.providers.get(provider_name)
    kind = provider_cfg.kind if provider_cfg and provider_cfg.kind else provider_name
    try:
        provider = build_provider(
            kind,
            api_key_env=provider_cfg.api_key_env if provider_cfg else None,
            base_url=provider_cfg.base_url if provider_cfg else None,
        )
    except UnknownProviderError as exc:
        console.print(f"[red]error:[/] {exc}")
        raise typer.Exit(code=1)

    run_id = resume or _new_run_id()
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    results_path = run_dir / "results.jsonl"

    run_config = RunConfig(
        model=bare_model,
        default_graders=config.graders,
        params=config.params,
        repeats=repeats or config.repeats,
        concurrency=concurrency or config.concurrency,
    )

    total_jobs = len(cases) * run_config.repeats
    progress, task_id = make_progress(total_jobs)
    running_cost = 0.0
    running_passed = 0
    running_n = 0

    def on_result(result: Result) -> None:
        nonlocal running_cost, running_passed, running_n
        running_cost += result.cost_usd
        running_passed += int(result.passed)
        running_n += 1
        progress.update(
            task_id,
            advance=1,
            cost=running_cost,
            pass_rate=(running_passed / running_n) if running_n else 0.0,
        )

    with progress:
        asyncio.run(
            run_suite(
                cases, provider, run_config, results_path, resume=bool(resume), on_result=on_result
            )
        )

    # Totals cover the run's full on-disk history, not just rows written this
    # invocation — matters when --resume only redid a subset.
    all_results = _load_all_results(results_path)

    case_hashes = compute_case_hashes(cases)
    model_resolved = next(
        (r.response.model_resolved for r in all_results if r.response and r.response.model_resolved),
        None,
    )
    manifest = RunManifest(
        run_id=run_id,
        anchor_version=__version__,
        suite_hash=suite_hash(case_hashes),
        case_count=len(cases),
        case_hashes=case_hashes,
        provider=provider_name,
        model=bare_model,
        model_resolved=model_resolved,
        params=run_config.params,
        repeats=run_config.repeats,
        totals=aggregate_totals(all_results),
        env=EnvInfo(python=platform.python_version(), os=platform.platform()),
        git=_git_info(config_path.parent),
        notes=name,
        tags=list(tags),
    )
    (run_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    print_manifest_summary(console, manifest)

    error_count = sum(1 for r in all_results if r.status == "provider_error")
    if all_results and error_count / len(all_results) > _PROVIDER_ERROR_EXIT_THRESHOLD:
        console.print(f"[red]{error_count}/{len(all_results)} results were provider errors[/]")
        raise typer.Exit(code=3)


runs_app = typer.Typer(help="List and inspect past runs.")


def _resolve_run_ref(ref: str) -> str:
    """run_id or `@latest`. The full grammar (`@baseline[:name]`, `-N`) lands
    with `bless`/`compare` in P2 (§8)."""
    if ref != "@latest":
        return ref
    manifests = sorted(RUNS_DIR.glob("*/manifest.json"), key=lambda p: p.stat().st_mtime)
    if not manifests:
        raise typer.BadParameter("no runs exist yet")
    return manifests[-1].parent.name


@runs_app.command("list")
def list_runs() -> None:
    if not RUNS_DIR.exists() or not any(RUNS_DIR.glob("*/manifest.json")):
        console.print("no runs yet — try `anchor run`")
        return

    manifests = []
    for manifest_path in RUNS_DIR.glob("*/manifest.json"):
        try:
            manifests.append(RunManifest.model_validate_json(manifest_path.read_text(encoding="utf-8")))
        except Exception:
            continue
    manifests.sort(key=lambda m: m.created_at, reverse=True)

    table = Table(title=f"{len(manifests)} run(s)")
    for col in ("run_id", "provider:model", "score", "pass rate", "cost", "cases", "created_at"):
        table.add_column(col)
    for m in manifests:
        table.add_row(
            m.run_id,
            f"{m.provider}:{m.model}",
            f"{m.totals.score:.1%}",
            f"{m.totals.pass_rate:.1%}",
            f"${m.totals.cost_usd:.4f}",
            str(m.case_count),
            m.created_at.isoformat(timespec="seconds"),
        )
    console.print(table)


@runs_app.command("show")
def show_run(ref: str = typer.Argument(..., help="run_id or @latest")) -> None:
    run_id = _resolve_run_ref(ref)
    manifest_path = RUNS_DIR / run_id / "manifest.json"
    if not manifest_path.exists():
        console.print(f"[red]error:[/] no run {run_id!r} in {RUNS_DIR}")
        raise typer.Exit(code=1)
    manifest = RunManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    print_manifest_summary(console, manifest)
