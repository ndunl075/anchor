from __future__ import annotations

import importlib.util
from pathlib import Path
from anchor.core.models import Case, Response, Verdict
from anchor.graders.base import GraderContext

class PythonFnGrader:
    kind = "python_fn"; version = "1"
    def __init__(self, config: dict): self.target = str(config.get("target", ""))
    async def grade(self, case: Case, resp: Response, ctx: GraderContext) -> Verdict:
        path, _, name = self.target.partition("::")
        if not path or not name: raise ValueError("python_fn requires config.target='file.py::function'")
        spec = importlib.util.spec_from_file_location("anchor_user_grader", Path(path))
        if not spec or not spec.loader: raise ValueError(f"can't load {path}")
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        result = getattr(module, name)(case, resp)
        if isinstance(result, Verdict): return result
        passed = bool(result)
        return Verdict(grader=self.kind, score=float(passed), passed=passed)
