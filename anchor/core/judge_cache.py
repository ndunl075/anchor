"""Content-addressed local cache for pinned judge verdicts (Architecture §6.3)."""
from __future__ import annotations

import os
import uuid
from pathlib import Path

from anchor.core.models import Verdict
from anchor.core.suite import canonical_json, short_hash


def judge_cache_key(
    judge_model: str, prompt_hash: str, case_hash: str, response_text_hash: str
) -> str:
    return short_hash(canonical_json({
        "judge_model": judge_model,
        "prompt_hash": prompt_hash,
        "case_hash": case_hash,
        "response_text_hash": response_text_hash,
    }))


class JudgeCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)

    def _path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get(self, key: str) -> Verdict | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            return Verdict.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def put(self, key: str, verdict: Verdict) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        target = self._path(key)
        temporary = target.with_suffix(f".{uuid.uuid4().hex}.tmp")
        temporary.write_text(verdict.model_dump_json(), encoding="utf-8")
        os.replace(temporary, target)
