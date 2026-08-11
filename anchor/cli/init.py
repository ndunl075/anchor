"""`anchor init` — scaffold anchor.yaml + cases/ + one example case (§8)."""
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

console = Console()

_ANCHOR_YAML = """\
version: 1
suite: cases/*.jsonl

model: claude-opus-5
providers:
  anthropic: { api_key_env: ANTHROPIC_API_KEY }

params: { temperature: 0, max_tokens: 1024 }
repeats: 1
concurrency: 8

graders:
  - kind: exact
"""

_EXAMPLE_CASE = (
    '{"id": "example-1", "input": "What is 2+2? Answer with just the number.", '
    '"expect": "4", "tags": ["example"]}\n'
)


def _ensure_line(path: Path, line: str) -> None:
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    if line in existing:
        return
    existing.append(line)
    path.write_text("\n".join(existing) + "\n", encoding="utf-8")
    console.print(f"[green]update[/] {path}")


def init(
    directory: Path = typer.Argument(Path("."), help="Project directory (created if missing)."),
    track_runs: bool = typer.Option(
        True,
        "--track-runs/--no-track-runs",
        help="Commit .anchor/runs (default: yes — replay is first-class, §1). "
        "--no-track-runs gitignores it instead.",
    ),
) -> None:
    """Scaffold anchor.yaml, cases/, and .anchor/ in DIRECTORY."""
    cases_dir = directory / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    (directory / ".anchor" / "runs").mkdir(parents=True, exist_ok=True)
    (directory / ".anchor" / "cache").mkdir(parents=True, exist_ok=True)

    anchor_yaml = directory / "anchor.yaml"
    if anchor_yaml.exists():
        console.print(f"[yellow]skip[/] {anchor_yaml} already exists")
    else:
        anchor_yaml.write_text(_ANCHOR_YAML, encoding="utf-8")
        console.print(f"[green]create[/] {anchor_yaml}")

    example_case = cases_dir / "example.jsonl"
    if example_case.exists():
        console.print(f"[yellow]skip[/] {example_case} already exists")
    else:
        example_case.write_text(_EXAMPLE_CASE, encoding="utf-8")
        console.print(f"[green]create[/] {example_case}")

    gitignore = directory / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("", encoding="utf-8")
    _ensure_line(gitignore, ".anchor/cache/")
    if not track_runs:
        _ensure_line(gitignore, ".anchor/runs/")

    console.print("\n[bold]Next:[/] set your provider API key, then:")
    console.print("  anchor run")
