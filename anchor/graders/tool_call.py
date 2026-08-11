from __future__ import annotations

from anchor.core.models import Case, Response, Verdict
from anchor.graders.base import GraderContext

class ToolCallGrader:
    kind = "tool_call"; version = "1"
    def __init__(self, config: dict): self.config = config
    async def grade(self, case: Case, resp: Response, ctx: GraderContext) -> Verdict:
        name, arguments = self.config.get("name"), self.config.get("arguments")
        passed = any(call.name == name and (arguments is None or call.arguments == arguments) for call in resp.tool_calls)
        return Verdict(grader=self.kind, score=float(passed), passed=passed)
