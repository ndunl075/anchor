"""`anchor compare <a> <b>` — the regression list between two runs (§7.2, §8).

Comparing runs deliberately doesn't hard-require a live anchor.yaml/suite —
you should be able to compare two runs from months ago even if the project's
config has since moved on. Config/suite are used opportunistically (drift
threshold, fail_on_regression, per-tag breakdown) and silently skipped if
unavailable.
"""
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from anchor.cli._common import load_manifest, load_results, resolve_run_ref
from anchor.core.compare import Classification, CaseDiff, CompareReport, compare_runs, sort_diffs_for_display, tag_breakdown
from anchor.core.config import ConfigError, load_config
from anchor.core.suite import SuiteError, load_suite
from anchor.report.terminal import print_compare_summary

console = Console()

_DEFAULT_DRIFT_THRESHOLD = 0.15


def compare(
    run_a: str = typer.Argument(..., help="run_id or a ref: @latest, @baseline[:name], -N"),
    run_b: str = typer.Argument(..., help="run_id or a ref: @latest, @baseline[:name], -N"),
    config_path: Path = typer.Option(Path("anchor.yaml"), "--config", "-c"),
    threshold: float = typer.Option(
        0.0, "--threshold", help="Drift threshold override (0 = use anchor.yaml, default 0.15)."
    ),
    fmt: str = typer.Option("term", "--format", help="term | json | md"),
    only: str = typer.Option("", "--only", help="Only show this classification, e.g. regression."),
) -> None:
    id_a, id_b = resolve_run_ref(run_a), resolve_run_ref(run_b)
    manifest_a, manifest_b = load_manifest(id_a), load_manifest(id_b)
    results_a, results_b = load_results(id_a), load_results(id_b)

    drift_threshold = threshold
    fail_on_regression = True
    case_tags: dict[str, list[str]] = {}
    try:
        config = load_config(config_path)
        fail_on_regression = config.compare.fail_on_regression
        if not drift_threshold:
            drift_threshold = config.compare.drift_threshold
        cases = load_suite(config.suite, config_path.parent)
        case_tags = {c.id: c.tags for c in cases}
    except (ConfigError, SuiteError):
        pass  # no live config/suite — deltas and classification still work fine
    if not drift_threshold:
        drift_threshold = _DEFAULT_DRIFT_THRESHOLD

    report = compare_runs(manifest_a, results_a, manifest_b, results_b, drift_threshold)
    diffs = sort_diffs_for_display(report.diffs)
    if only:
        wanted = only.strip().upper()
        diffs = [d for d in diffs if d.classification.value == wanted]

    tag_stats = tag_breakdown(report.diffs, case_tags) if case_tags else {}

    if manifest_a.suite_hash != manifest_b.suite_hash:
        console.print(
            "[yellow]warning: suite_hash differs between these runs — comparison covers only "
            "the intersection of cases (see CHANGED/MISSING below)[/]"
        )

    if fmt == "json":
        console.print_json(data=_to_jsonable(report, diffs, tag_stats))
    elif fmt == "md":
        print(_to_markdown(report, diffs, tag_stats))
    else:
        print_compare_summary(console, report, diffs, tag_stats)

    if fail_on_regression and report.counts[Classification.REGRESSION.value] > 0:
        raise typer.Exit(code=2)


def _to_jsonable(report: CompareReport, diffs: list[CaseDiff], tag_stats: dict[str, dict]) -> dict:
    return {
        "run_a": report.run_a.run_id,
        "run_b": report.run_b.run_id,
        "delta_score": report.delta_score,
        "delta_score_ci": list(report.delta_score_ci),
        "significant": report.significant,
        "delta_cost_usd": report.delta_cost_usd,
        "delta_p95_latency_ms": report.delta_p95_latency,
        "counts": report.counts,
        "diffs": [
            {
                "case_id": d.case_id,
                "classification": d.classification.value,
                "score_a": d.score_a,
                "score_b": d.score_b,
                "delta": d.delta,
                "note": d.note,
            }
            for d in diffs
        ],
        "tag_breakdown": tag_stats,
    }


def _to_markdown(report: CompareReport, diffs: list[CaseDiff], tag_stats: dict[str, dict]) -> str:
    counts_str = ", ".join(f"{k}={v}" for k, v in report.counts.items() if v) or "none"
    lines = [
        f"## Compare: `{report.run_a.run_id}` -> `{report.run_b.run_id}`",
        "",
        f"- Δ score: {report.delta_score:+.1%} (95% CI {report.delta_score_ci[0]:+.1%} to {report.delta_score_ci[1]:+.1%}; {'significant' if report.significant else 'not significant'})",
        f"- Δ cost: ${report.delta_cost_usd:+.4f}",
        f"- Δ p95 latency: {report.delta_p95_latency:+.0f} ms",
        f"- counts: {counts_str}",
        "",
        "| case_id | class | score A | score B | Δ | note |",
        "|---|---|---|---|---|---|",
    ]
    for d in diffs:
        score_a = f"{d.score_a:.1%}" if d.score_a is not None else "-"
        score_b = f"{d.score_b:.1%}" if d.score_b is not None else "-"
        delta = f"{d.delta:+.1%}" if d.delta is not None else "-"
        lines.append(f"| {d.case_id} | {d.classification.value} | {score_a} | {score_b} | {delta} | {d.note} |")
    if tag_stats:
        lines += ["", "| tag | n | regressions | fixes | mean Δ |", "|---|---|---|---|---|"]
        for tag, stats in sorted(tag_stats.items()):
            lines.append(
                f"| {tag} | {stats['n']} | {stats['regressions']} | {stats['fixes']} | "
                f"{stats['mean_delta']:+.1%} |"
            )
    return "\n".join(lines)
