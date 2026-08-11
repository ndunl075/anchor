"""`regex` grader (§5.3): passes iff resp.text matches config.pattern."""
from __future__ import annotations

import re

from anchor.core.models import Case, Response, Verdict
from anchor.graders.base import GraderContext

_FLAG_MAP = {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL, "x": re.VERBOSE}


class RegexGrader:
    kind = "regex"
    version = "1"

    def __init__(self, config: dict | None = None):
        config = config or {}
        pattern = config.get("pattern")
        if not pattern:
            raise ValueError("regex grader requires config.pattern")

        flags = 0
        for flag in config.get("flags", []):
            flags |= _FLAG_MAP.get(flag, 0)

        self.fullmatch: bool = config.get("fullmatch", False)
        self._compiled = re.compile(pattern, flags)

    async def grade(self, case: Case, resp: Response, ctx: GraderContext) -> Verdict:
        match = (
            self._compiled.fullmatch(resp.text)
            if self.fullmatch
            else self._compiled.search(resp.text)
        )
        passed = match is not None
        return Verdict(
            grader=self.kind,
            score=1.0 if passed else 0.0,
            passed=passed,
            rationale="" if passed else f"pattern {self._compiled.pattern!r} did not match",
        )
