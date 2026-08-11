"""Seeded paired bootstrap statistics over cases, never individual repeats (§7.4)."""
from __future__ import annotations

import numpy as np


def paired_bootstrap_ci(deltas: list[float], samples: int = 10_000, seed: int = 0) -> tuple[float, float]:
    if not deltas:
        return (0.0, 0.0)
    values = np.asarray(deltas, dtype=float)
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(values), size=(samples, len(values)))
    low, high = np.percentile(values[indices].mean(axis=1), (2.5, 97.5))
    return float(low), float(high)
