"""`anchor cases list|validate` — inspect a suite with no network calls (§8)."""
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from anchor.core.config import ConfigError, load_config, resolve_provider_name
from anchor.core.suite import SuiteError, case_hash, load_suite
from anchor.graders.registry import available_graders
from anchor.providers.registry import available_providers

app = typer.Typer(help="Inspect and validate the case suite.")
console = Console()


@app.command("list")
def list_cases(
    config_path: Path = typer.Option(Path("anchor.yaml"), "--config", "-c"),
    tag: str = typer.Option("", "--tag", help="Only show cases with this tag."),
) -> None:
    try:
        config = load_config(config_path)
        cases = load_suite(config.suite, config_path.parent)
    except (ConfigError, SuiteError) as exc:
        console.print(f"[red]error:[/] {exc}")
        raise typer.Exit(code=1)

    if tag:
        cases = [c for c in cases if tag in c.tags]

    table = Table(title=f"{len(cases)} case(s)")
    table.add_column("id")
    table.add_column("tags")
    table.add_column("graders")
    table.add_column("hash")
    for case in cases:
        graders = ", ".join(g.kind for g in case.graders) or "(suite default)"
        table.add_row(case.id, ", ".join(case.tags), graders, case_hash(case))
    console.print(table)


@app.command("validate")
def validate_cases(
    config_path: Path = typer.Option(Path("anchor.yaml"), "--config", "-c"),
) -> None:
    """Hash check + grader/provider resolution. No network (§8)."""
    try:
        config = load_config(config_path)
        cases = load_suite(config.suite, config_path.parent)
    except (ConfigError, SuiteError) as exc:
        console.print(f"[red]error:[/] {exc}")
        raise typer.Exit(code=1)

    known_graders = available_graders()
    known_providers = available_providers()
    problems: list[str] = []

    for case in cases:
        specs = case.graders or config.graders
        if not specs:
            problems.append(f"{case.id}: no graders (case declares none and the suite default is empty)")
        for spec in specs:
            if spec.kind not in known_graders:
                problems.append(f"{case.id}: unknown grader kind {spec.kind!r}")

    if config.model:
        try:
            provider_name, _ = resolve_provider_name(config.model, config)
            override = config.providers.get(provider_name)
            kind = override.kind if override and override.kind else provider_name
            if kind not in known_providers:
                problems.append(f"default model {config.model!r}: unknown provider {kind!r}")
        except ConfigError as exc:
            problems.append(str(exc))

    console.print(f"{len(cases)} case(s), {len(problems)} problem(s)")
    for problem in problems:
        console.print(f"  [red]x[/] {problem}")
    if problems:
        raise typer.Exit(code=1)
    console.print("[green]ok[/]")
