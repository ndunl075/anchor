from __future__ import annotations

import json
from anchor.core.models import Case, Response, Verdict
from anchor.graders.base import GraderContext

class JsonPathGrader:
    kind = "json_path"; version = "1"
    def __init__(self, config: dict): self.config = config
    async def grade(self, case: Case, resp: Response, ctx: GraderContext) -> Verdict:
        try:
            value = json.loads(resp.text)
            for key in str(self.config.get("path", "")).lstrip("$").strip(".").split("."):
                if key: value = value[key]
            expected = self.config.get("expect", case.expect)
            passed = value == expected
            return Verdict(grader=self.kind, score=float(passed), passed=passed, rationale=f"extracted {value!r}")
        except (json.JSONDecodeError, KeyError, TypeError) as exc: return Verdict(grader=self.kind, score=0, passed=False, error=str(exc))
