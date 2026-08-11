from __future__ import annotations
from pathlib import Path
import typer
from rich.console import Console
from anchor.cli._common import load_manifest, load_results, resolve_run_ref
from anchor.report.html import write_html
console = Console()
def report(refs: list[str] = typer.Argument(..., help="One or more run ids or refs."), html: Path = typer.Option(Path("anchor-report.html"), "--html")) -> None:
    """Write a standalone, offline HTML report with embedded run data."""
    ids = [resolve_run_ref(ref) for ref in refs]
    manifests = [load_manifest(run_id) for run_id in ids]
    write_html(html, manifests, {run_id: load_results(run_id) for run_id in ids})
    console.print(f"[green]wrote[/] {html}")
