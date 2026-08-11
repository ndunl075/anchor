"""grader kind -> class. Built-ins only for now; §5.3 lists json_schema,
json_path, numeric, latency, cost, tool_call, python_fn, llm_judge, pairwise
as later additions (P3/P4 per the §10 build order) — add them here as they land.
"""
from __future__ import annotations

from anchor.core.models import GraderSpec
from anchor.graders.base import Grader
from anchor.graders.contains import ContainsGrader
from anchor.graders.exact import ExactGrader
from anchor.graders.regex import RegexGrader

_BUILTIN: dict[str, type] = {
    "exact": ExactGrader,
    "contains": ContainsGrader,
    "regex": RegexGrader,
}


class UnknownGraderError(Exception):
    pass


def available_graders() -> dict[str, type]:
    return dict(_BUILTIN)


def build_grader(spec: GraderSpec) -> Grader:
    registry = available_graders()
    try:
        cls = registry[spec.kind]
    except KeyError:
        known = ", ".join(sorted(registry)) or "(none registered)"
        raise UnknownGraderError(f"unknown grader kind {spec.kind!r}. Known: {known}") from None
    return cls(spec.config)
