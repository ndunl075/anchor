"""name -> Provider class, plus third-party discovery via entry points (§5.1)."""
from __future__ import annotations

from importlib.metadata import entry_points

from anchor.providers.anthropic import AnthropicProvider
from anchor.providers.openai import OpenAIProvider

ENTRY_POINT_GROUP = "anchor.providers"

_BUILTIN: dict[str, type] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
}


class UnknownProviderError(Exception):
    pass


def available_providers() -> dict[str, type]:
    """Built-ins plus any third-party provider packages registered under the
    `anchor.providers` entry-point group. Built-ins win on name collision.
    """
    registry: dict[str, type] = {}
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        registry[ep.name] = ep.load()
    registry.update(_BUILTIN)
    return registry


def get_provider_class(name: str) -> type:
    registry = available_providers()
    try:
        return registry[name]
    except KeyError:
        known = ", ".join(sorted(registry)) or "(none registered)"
        raise UnknownProviderError(f"unknown provider {name!r}. Known providers: {known}") from None


def build_provider(
    kind: str, *, api_key_env: str | None = None, base_url: str | None = None
) -> object:
    """Instantiate a provider by registry key, applying only the overrides the
    caller actually set (adapters keep their own defaults otherwise). Kept
    decoupled from `core.config.ProviderConfig` on purpose — this module has
    no reason to know about YAML.
    """
    cls = get_provider_class(kind)
    kwargs: dict[str, str] = {}
    if api_key_env:
        kwargs["api_key_env"] = api_key_env
    if base_url:
        kwargs["base_url"] = base_url
    return cls(**kwargs)
