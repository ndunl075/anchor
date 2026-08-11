from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load(path: Path) -> list[dict[str, Any]]:
    records = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"{path}:{lineno}: each JSONL row must be an object")
        records.append(record)
    return records
