"""anchor.yaml loading and model -> provider resolution. See ARCHITECTURE.md §9.

Model routing: `--model claude-opus-5` has no explicit provider. Resolution is
a name-prefix heuristic (claude* -> anthropic, gpt*/o1*/o3*/o4* -> openai) with
an explicit `<provider>:<model>` escape hatch for anything the heuristic can't
place — this was an open call, resolved in favor of the heuristic for the
common case plus the explicit form when it's wrong or ambiguous.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from anchor.core.models import GraderSpec

DEFAULT_CONFIG_FILENAME = "anchor.yaml"

_MODEL_PREFIX_TO_PROVIDER: dict[str, str] = {
    "claude": "anthropic",
    "gpt": "openai",
    "o1": "openai",
    "o3": "openai",
    "o4": "openai",
}


class ConfigError(Exception):
    pass


class ProviderConfig(BaseModel):
    kind: str | None = None  # defaults to the provider's registry key
    api_key_env: str | None = None
    base_url: str | None = None


class JudgeConfig(BaseModel):
    model: str | None = None
    temperature: float = 0.0
    calibration_suite: str = "cases/calibration.jsonl"


class CompareConfig(BaseModel):
    drift_threshold: float = 0.15
    fail_on_regression: bool = True


class RedactRule(BaseModel):
    pattern: str
    replace: str


class Config(BaseModel):
    version: int = 1
    suite: str = "cases/*.jsonl"
    model: str | None = None
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    repeats: int = 1
    concurrency: int = 8
    graders: list[GraderSpec] = Field(default_factory=list)
    judge: JudgeConfig = Field(default_factory=JudgeConfig)
    compare: CompareConfig = Field(default_factory=CompareConfig)
    redact: list[RedactRule] = Field(default_factory=list)
    pricing_overrides: dict[str, dict[str, float]] = Field(default_factory=dict)


def load_config(path: str | Path = DEFAULT_CONFIG_FILENAME) -> Config:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"{path} not found. Run `anchor init` to scaffold one.")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: invalid YAML: {exc}") from exc
    try:
        return Config.model_validate(raw)
    except Exception as exc:  # pydantic.ValidationError, kept untyped to avoid the import
        raise ConfigError(f"{path}: invalid config: {exc}") from exc


def resolve_provider_name(model: str, config: Config) -> tuple[str, str]:
    """Return `(provider_name, bare_model_name)` for a `--model` value."""
    if ":" in model:
        provider_name, _, bare_model = model.partition(":")
        return provider_name, bare_model

    lowered = model.lower()
    for prefix, provider_name in _MODEL_PREFIX_TO_PROVIDER.items():
        if lowered.startswith(prefix):
            return provider_name, model

    known = ", ".join(sorted(set(_MODEL_PREFIX_TO_PROVIDER.values())))
    raise ConfigError(
        f"can't infer a provider for model {model!r}. Recognized prefixes route "
        f"to: {known}. Use the explicit '<provider>:<model>' form instead, "
        f"e.g. 'anthropic:{model}'."
    )
