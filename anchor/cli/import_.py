"""`anchor import` — turn local traffic logs into redacted, frozen JSONL cases."""
from __future__ import annotations

import random
from pathlib import Path

import typer
from rich.console import Console

from anchor.core.config import ConfigError, load_config
from anchor.importers import csv_ as csv_importer
from anchor.importers import jsonl as jsonl_importer
from anchor.importers import openai_log as openai_importer
from anchor.importers.common import case_from_record

console = Console()


def import_logs(
    source: Path = typer.Argument(..., exists=True, dir_okay=False),
    format: str = typer.Option("jsonl", "--format"),
    mappings: list[str] = typer.Option([], "--map", help="e.g. input=.messages or id=.request_id"),
    limit: int = typer.Option(0, "--limit", min=0),
    sample: int = typer.Option(0, "--sample", min=0),
    output: Path | None = typer.Option(None, "--output", "-o"),
    config_path: Path = typer.Option(Path("anchor.yaml"), "--config", "-c"),
) -> None:
    """Import local traffic only; no labels are required for baseline mode."""
    try:
        config = load_config(config_path)
        if format not in {"jsonl", "openai", "csv"}:
            raise ValueError("--format must be jsonl, openai, or csv")
        records = (
            csv_importer.load(source) if format == "csv"
            else openai_importer.load(source) if format == "openai"
            else jsonl_importer.load(source)
        )
        field_map = {}
        for mapping in mappings:
            field, equals, path = mapping.partition("=")
            if not equals or not field or not path:
                raise ValueError(f"invalid --map {mapping!r}; use field=.path")
            field_map[field] = path
        if sample:
            records = random.Random(0).sample(records, min(sample, len(records)))
        if limit:
            records = records[:limit]
        cases = [case_from_record(row, index, field_map, config.redact) for index, row in enumerate(records)]
        if len({case.id for case in cases}) != len(cases):
            raise ValueError("import produced duplicate ids; pass --map id=.your_unique_id")
    except (ConfigError, ValueError) as exc:
        console.print(f"[red]error:[/] {exc}")
        raise typer.Exit(code=1)

    destination = output or Path("cases") / f"imported-{source.stem}.jsonl"
    if not destination.is_absolute():
        destination = config_path.parent / destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("".join(case.model_dump_json() + "\n" for case in cases), encoding="utf-8")
    console.print(f"[green]imported[/] {len(cases)} redacted case(s) to {destination}")
