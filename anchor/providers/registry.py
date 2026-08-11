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
