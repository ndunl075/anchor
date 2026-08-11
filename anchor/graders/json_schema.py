from __future__ import annotations

import json
from anchor.core.models import Case, Response, Verdict
from anchor.graders.base import GraderContext

class JsonSchemaGrader:
    kind = "json_schema"; version = "1"
    def __init__(self, config: dict): self.schema = config.get("schema", {})
    async def grade(self, case: Case, resp: Response, ctx: GraderContext) -> Verdict:
        try:
            value = json.loads(resp.text)
            required = self.schema.get("required", [])
            properties = self.schema.get("properties", {})
            valid = isinstance(value, dict) and all(key in value for key in required)
            for key, spec in properties.items():
                if key in value and spec.get("type") == "string" and not isinstance(value[key], str): valid = False
                if key in value and spec.get("type") == "number" and not isinstance(value[key], (int, float)): valid = False
            return Verdict(grader=self.kind, score=float(valid), passed=valid, rationale="valid JSON schema subset" if valid else "schema mismatch")
        except json.JSONDecodeError as exc: return Verdict(grader=self.kind, score=0, passed=False, error=str(exc))
