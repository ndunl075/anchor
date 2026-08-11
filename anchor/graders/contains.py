"""`contains` grader (§5.3): any/all/none of a set of substrings in resp.text.

Needles come from `case.expect` by default (a str or list[str]); override with
`config.values` when the case's `expect` is used for something else.
"""
from __future__ import annotations

from anchor.core.models import Case, Response, Verdict
from anchor.graders.base import GraderContext

_MODES = {"any", "all", "none"}


class ContainsGrader:
    kind = "contains"
    version = "1"

    def __init__(self, config: dict | None = None):
        config = config or {}
        self.mode: str = config.get("mode", "any")
        if self.mode not in _MODES:
            raise ValueError(f"contains grader: mode must be one of {sorted(_MODES)}, got {self.mode!r}")
        self.case_sensitive: bool = config.get("case_sensitive", True)
        self._config_values = config.get("values")

    def _needles(self, case: Case) -> list[str]:
        values = self._config_values if self._config_values is not None else case.expect
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise ValueError(
                "contains grader requires case.expect (or config.values) to be a str or list[str]"
            )
        return values

    async def grade(self, case: Case, resp: Response, ctx: GraderContext) -> Verdict:
        try:
            needles = self._needles(case)
        except ValueError as exc:
            return Verdict(grader=self.kind, score=0.0, passed=False, error=str(exc))

        haystack = resp.text if self.case_sensitive else resp.text.lower()
        candidates = needles if self.case_sensitive else [n.lower() for n in needles]
        hits = [n for n, c in zip(needles, candidates) if c in haystack]

        if self.mode == "any":
            passed = len(hits) > 0
        elif self.mode == "all":
            passed = len(hits) == len(needles)
        else:  # none
            passed = len(hits) == 0

        return Verdict(
            grader=self.kind,
            score=1.0 if passed else 0.0,
            passed=passed,
            rationale=f"mode={self.mode} matched={hits}",
        )
