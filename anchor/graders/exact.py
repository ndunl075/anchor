"""`exact` grader (§5.3): passes iff resp.text equals case.expect exactly."""
from __future__ import annotations

from anchor.core.models import Case, Response, Verdict
from anchor.graders.base import GraderContext


class ExactGrader:
    kind = "exact"
    version = "1"

    def __init__(self, config: dict | None = None):
        config = config or {}
        self.case_sensitive: bool = config.get("case_sensitive", True)
        self.strip: bool = config.get("strip", True)

    async def grade(self, case: Case, resp: Response, ctx: GraderContext) -> Verdict:
        if not isinstance(case.expect, str):
            return Verdict(
                grader=self.kind,
                score=0.0,
                passed=False,
                error=f"exact grader requires case.expect: str, got {type(case.expect).__name__}",
            )

        actual, expected = resp.text, case.expect
        if self.strip:
            actual, expected = actual.strip(), expected.strip()
        if not self.case_sensitive:
            actual, expected = actual.lower(), expected.lower()

        passed = actual == expected
        return Verdict(
            grader=self.kind,
            score=1.0 if passed else 0.0,
            passed=passed,
            rationale="" if passed else f"expected {expected!r}, got {actual!r}",
        )
