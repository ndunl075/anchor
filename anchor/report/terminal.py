"""Terminal rendering: live run progress and post-run summary (§6.1, §7.4).

§7.4 caps every reported percentage at 1 decimal place — enforced here so no
call site has to remember it.
"""
from __future__ import annotations

from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn
from rich.table import Table

from anchor.core.compare import CaseDiff, CompareReport
from anchor.core.models import RunManifest

# §7.4: "Warn when case_count < 30 that CIs are wide and the regression list
# matters more." No CI exists yet (P4), but the underlying caution — small
# suites make any single delta anecdotal — applies just as much to a bare
# point estimate, so the warning fires here too.
_SMALL_SUITE_THRESHOLD = 30


def make_progress(total: int) -> tuple[Progress, int]:
    """A rich Progress with completed/total, running cost, running pass rate,
    and elapsed time (ETA needs a stable rate estimate rich already provides
    via elapsed + total; a dedicated ETA column can follow if it's not enough).
    """
    progress = Progress(
        TextColumn("[bold]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TextColumn("cost=${task.fields[cost]:.4f}"),
        TextColumn("pass={task.fields[pass_rate]:.1%}"),
        TimeElapsedColumn(),
    )
    task_id = progress.add_task("running", total=total, cost=0.0, pass_rate=0.0)
    return progress, task_id


def print_manifest_summary(console: Console, manifest: RunManifest) -> None:
    table = Table(title=f"run {manifest.run_id}")
    table.add_column("metric")
    table.add_column("value")
    table.add_row("model", f"{manifest.provider}:{manifest.model}")
    if manifest.model_resolved:
        table.add_row("model_resolved", manifest.model_resolved)
    table.add_row("cases", str(manifest.case_count))
    table.add_row("score", f"{manifest.totals.score:.1%}")
    table.add_row("pass rate", f"{manifest.totals.pass_rate:.1%}")
    table.add_row("cost", f"${manifest.totals.cost_usd:.4f}")
    table.add_row("p50 latency", f"{manifest.totals.p50_latency:.0f} ms")
    table.add_row("p95 latency", f"{manifest.totals.p95_latency:.0f} ms")
    table.add_row("tokens in/out", f"{manifest.totals.tokens_in}/{manifest.totals.tokens_out}")
    console.print(table)


def _fmt_pct(value: float | None) -> str:
    return f"{value:.1%}" if value is not None else "-"


def _fmt_delta_pct(value: float | None) -> str:
    return f"{value:+.1%}" if value is not None else "-"


def print_compare_summary(
    console: Console,
    report: CompareReport,
    diffs: list[CaseDiff],
    tag_stats: dict[str, dict] | None = None,
) -> None:
    """Headline (Δscore, Δcost, Δp95 latency, counts — never Δscore alone,
    §7.2) + per-case diff table + optional per-tag breakdown."""
    headline = Table(title=f"{report.run_a.run_id} -> {report.run_b.run_id}", show_header=False)
    headline.add_column("metric")
    headline.add_column("value")
    headline.add_row("Δ score", f"{report.delta_score:+.1%} (95% CI {report.delta_score_ci[0]:+.1%} to {report.delta_score_ci[1]:+.1%}; {'significant' if report.significant else 'not significant'})")
    headline.add_row("Δ cost", f"${report.delta_cost_usd:+.4f}")
    headline.add_row("Δ p95 latency", f"{report.delta_p95_latency:+.0f} ms")
    counts_str = ", ".join(f"{k}={v}" for k, v in report.counts.items() if v) or "no cases compared"
    headline.add_row("counts", counts_str)
    console.print(headline)

    if 0 < len(diffs) < _SMALL_SUITE_THRESHOLD:
        console.print(
            f"[yellow]small suite ({len(diffs)} cases) — treat any score delta as anecdotal; "
            "the regression list below matters more.[/]"
        )

    table = Table(title="case diffs")
    for col in ("case_id", "class", "score A", "score B", "Δ", "note"):
        table.add_column(col)
    for d in diffs:
        table.add_row(
            d.case_id,
            d.classification.value,
            _fmt_pct(d.score_a),
            _fmt_pct(d.score_b),
            _fmt_delta_pct(d.delta),
            d.note,
        )
    console.print(table)

    if tag_stats:
        tag_table = Table(title="per-tag breakdown")
        for col in ("tag", "n", "regressions", "fixes", "mean Δ"):
            tag_table.add_column(col)
        for tag, stats in sorted(tag_stats.items()):
            tag_table.add_row(
                tag, str(stats["n"]), str(stats["regressions"]), str(stats["fixes"]),
                _fmt_delta_pct(stats["mean_delta"]),
            )
        console.print(tag_table)
