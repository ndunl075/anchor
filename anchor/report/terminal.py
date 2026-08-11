"""Terminal rendering: live run progress and post-run summary (§6.1, §7.4).

§7.4 caps every reported percentage at 1 decimal place — enforced here so no
call site has to remember it.
"""
from __future__ import annotations

from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn
from rich.table import Table

from anchor.core.models import RunManifest


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
