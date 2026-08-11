"""Local price lookup and conservative dry-run estimates (§6.4)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10; overrides still work without a parser dependency.
    tomllib = None
def estimate_tokens(text: str) -> int: return max(1, (len(text) + 3) // 4)
def estimate_usd(model: str, input_tokens: int, max_output_tokens: int, overrides: dict[str, Any] | None = None) -> float | None:
    path = Path(__file__).parent.parent / "pricing.toml"
    data = tomllib.loads(path.read_text(encoding="utf-8")) if tomllib and path.exists() else {}
    price = (overrides or {}).get(model) or data.get("models", {}).get(model)
    if not price: return None
    return (input_tokens * float(price.get("input", 0)) + max_output_tokens * float(price.get("output", 0))) / 1_000_000
