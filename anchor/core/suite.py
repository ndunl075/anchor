"""Load, validate and hash suites of cases. See ARCHITECTURE.md §4.1 / §4.4.

Hashing is the trust anchor of the whole product: two runs are only comparable
if their case definitions are provably identical. Golden-test this module hard
(see §11) — a hash that drifts across a Python version or dict-ordering quirk
would silently corrupt every historical comparison.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ValidationError

from anchor.core.models import Case

# Case fields that participate in case_hash. Deliberately excludes id/tags/weight —
# those are metadata, and changing them must not invalidate history (§4.1).
_HASHED_FIELDS = ("input", "system", "expect", "graders", "params")


class SuiteError(Exception):
    """Raised for anything that makes a suite un-loadable or ambiguous:
    malformed JSONL, a case that fails schema validation, or a duplicate id.
    """


def _json_default(obj: object) -> object:
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    raise TypeError(f"object of type {type(obj).__name__} is not JSON serializable")


def canonical_json(obj: object) -> str:
    """Stable JSON encoding: sorted keys, fixed separators, no whitespace.
    Must be identical across Python versions and dict insertion order.
    """
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=_json_default,
    )


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def short_hash(text: str) -> str:
    """First 16 hex chars of sha256 — the `*_hash` convention used everywhere (§4)."""
    return sha256_hex(text)[:16]


def case_hash(case: Case) -> str:
    payload = {field: getattr(case, field) for field in _HASHED_FIELDS}
    return short_hash(canonical_json(payload))


def compute_case_hashes(cases: list[Case]) -> dict[str, str]:
    return {case.id: case_hash(case) for case in cases}


def suite_hash(case_hashes: dict[str, str]) -> str:
    """sha256 of the sorted `{case_id: case_hash}` map (§4.4). Two runs with equal
    suite_hash are directly comparable; unequal means partial comparison, loudly
    reported by `compare` (§7.2's `CHANGED`/`MISSING` classes).
    """
    ordered = dict(sorted(case_hashes.items()))
    return short_hash(canonical_json(ordered))


def load_suite(pattern: str, base_dir: str | Path = ".") -> list[Case]:
    """Load every case matched by `pattern` (relative to `base_dir`, e.g.
    "cases/*.jsonl") as JSONL — one Case per non-blank, non-comment line.

    Order: files sorted by path, lines in file order (arrival order downstream
    in results.jsonl mirrors this only loosely — readers should sort by
    `(case_id, repeat)` per §6.1, not rely on suite order).
    """
    base = Path(base_dir)
    paths = sorted(base.glob(pattern))
    if not paths:
        raise SuiteError(f"no case files matched {pattern!r} under {base}")

    cases: list[Case] = []
    first_seen_in: dict[str, Path] = {}
    for path in paths:
        for lineno, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SuiteError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
            try:
                case = Case.model_validate(data)
            except ValidationError as exc:
                raise SuiteError(f"{path}:{lineno}: invalid case: {exc}") from exc
            if case.id in first_seen_in:
                raise SuiteError(
                    f"duplicate case id {case.id!r}: seen in {first_seen_in[case.id]} "
                    f"and again in {path}:{lineno}. Case ids must be unique in a suite."
                )
            first_seen_in[case.id] = path
            cases.append(case)
    return cases
