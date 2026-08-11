"""Typer app wiring. Thin: parse, call core, render (§3)."""
from __future__ import annotations

import typer

from anchor import __version__
from anchor.cli import cases as cases_cli
from anchor.cli import compare as compare_cli
from anchor.cli import init as init_cli
from anchor.cli import import_ as import_cli
from anchor.cli import judge_check as judge_check_cli
from anchor.cli import report as report_cli
from anchor.cli import run as run_cli

app = typer.Typer(
    name="anchor",
    help="Replay your own prompts against any model. Private score, not a public leaderboard.",
    no_args_is_help=True,
)

app.command("init")(init_cli.init)
app.command("run")(run_cli.run)
app.command("compare")(compare_cli.compare)
app.command("import")(import_cli.import_logs)
app.command("judge-check")(judge_check_cli.judge_check)
app.command("report")(report_cli.report)
app.add_typer(run_cli.runs_app, name="runs")
app.add_typer(cases_cli.app, name="cases")


@app.command("version")
def version() -> None:
    typer.echo(__version__)


if __name__ == "__main__":
    app()
