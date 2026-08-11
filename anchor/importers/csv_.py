from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def load(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]
