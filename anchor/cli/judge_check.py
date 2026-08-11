"""`anchor judge-check` — verify a pinned judge against human calibration labels."""
from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console

from anchor.core.config import ConfigError, load_config, resolve_provider_name
from anchor.core.judge_cache import JudgeCache
from anchor.core.models import Response
from anchor.core.suite import SuiteError, load_suite
from anchor.graders.base import GraderContext
from anchor.graders.llm_judge import LLMJudgeGrader
from anchor.providers.registry import UnknownProviderError, build_provider

console = Console()


def judge_check(
    config_path: Path = typer.Option(Path("anchor.yaml"), "--config", "-c"),
    suite: str = typer.Option("", "--suite", help="Calibration JSONL override."),
) -> None:
    """Report judge/human agreement on a local labeled calibration suite.

    Each calibration case must set ``params.judge_response`` (the answer to
    evaluate) and ``params.human_passed`` (the human label). Cases can use
    their normal ``expect`` and LLM-judge rubric configuration.
    """
    try:
        config = load_config(config_path)
        if not config.judge.model:
            raise ValueError("judge.model is required")
        cases = load_suite(suite or config.judge.calibration_suite, config_path.parent)
        provider_name, model = resolve_provider_name(config.judge.model, config)
        provider_cfg = config.providers.get(provider_name)
        provider = build_provider(
            provider_cfg.kind if provider_cfg and provider_cfg.kind else provider_name,
            api_key_env=provider_cfg.api_key_env if provider_cfg else None,
            base_url=provider_cfg.base_url if provider_cfg else None,
        )
    except (ConfigError, SuiteError, UnknownProviderError, ValueError) as exc:
        console.print(f"[red]error:[/] {exc}")
        raise typer.Exit(code=1)

    invalid = [case.id for case in cases if "judge_response" not in case.params or "human_passed" not in case.params]
    if invalid:
        console.print("[red]error:[/] calibration cases require params.judge_response and params.human_passed: " + ", ".join(invalid))
        raise typer.Exit(code=1)

    rubric = next((spec.config.get("rubric") for case in cases for spec in case.graders if spec.kind == "llm_judge"), None)
    grader = LLMJudgeGrader({"rubric": rubric} if rubric else {})
    context = GraderContext(
        judge_provider=provider, judge_model=model,
        judge_cache=JudgeCache(config_path.parent / ".anchor" / "cache" / "judges"),
    )

    async def evaluate():
        return await asyncio.gather(*(
            grader.grade(case, Response(text=str(case.params["judge_response"])), context)
            for case in cases
        ))
    verdicts = asyncio.run(evaluate())
    agreement = sum(v.passed == bool(c.params["human_passed"]) for c, v in zip(cases, verdicts))
    errors = sum(v.error is not None for v in verdicts)
    console.print(
        f"judge agreement: {agreement}/{len(cases)} ({agreement / len(cases):.1%}); "
        f"judge errors: {errors}; model: {config.judge.model}"
    )
    if errors:
        raise typer.Exit(code=3)
