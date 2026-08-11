"""Content-addressed response cache. See ARCHITECTURE.md §6.2.

Key = sha256(provider, model, canonical(params), canonical(messages), provider.version).
`temperature > 0` still caches (that's the point of replay) but `repeat` is part
of the key so N repeats stay distinct. The spec's key formula doesn't list
`system` as a separate term, but omitting it would let cache hits leak across
different system prompts for the same user turn — a correctness bug, not a
simplification — so it's folded in here alongside `repeat`.

Cache entries live at `.anchor/cache/<hash>.json`, one `Response` per file.
`--no-cache` means "don't attach a cache at all" (skips both read and write);
`--refresh` attaches the cache but skips the read, overwriting whatever was
there on write.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

from anchor.core.models import Message, Response
from anchor.core.suite import canonical_json, short_hash


def cache_key(
    provider_name: str,
    provider_version: str,
    model: str,
    params: dict,
    messages: list[Message],
    system: str | None,
    repeat: int,
) -> str:
    payload = {
        "provider": provider_name,
        "provider_version": provider_version,
        "model": model,
        "params": params,
        "messages": messages,
        "system": system,
        "repeat": repeat,
    }
    return short_hash(canonical_json(payload))


class ResponseCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)

    def _path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get(self, key: str) -> Response | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            return Response.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            # A corrupt/partial cache file (e.g. killed mid-write) is a miss,
            # not a crash — the run just re-fetches it.
            return None

    def put(self, key: str, response: Response) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # Write-then-rename so a killed process never leaves a half-written
        # file that `get()` would have to detect and discard.
        tmp_path = self._path(key).with_suffix(f".{uuid.uuid4().hex}.tmp")
        tmp_path.write_text(response.model_dump_json(), encoding="utf-8")
        os.replace(tmp_path, self._path(key))
