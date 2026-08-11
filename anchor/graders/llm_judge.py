"""Pinned, cached rubric judge. The provider boundary keeps this provider-neutral."""
from __future__ import annotations

import json

from anchor.core.judge_cache import judge_cache_key
from anchor.core.models import Case, Message, Request, Response, Verdict
from anchor.core.suite import case_hash, canonical_json, short_hash
from anchor.graders.base import GraderContext

_PROMPT = """You are an exacting evaluation judge. Evaluate the candidate response against the user case and rubric.
Return only JSON with keys score (number 0 to 1), passed (boolean), and rationale (brief string).
Case input: {input}
Expected answer (may be null): {expect}
Rubric: {rubric}
Candidate response: {response}"""


class LLMJudgeGrader:
    kind = "llm_judge"
    version = "1"

    def __init__(self, config: dict):
        self.rubric = str(config.get("rubric", "Answer is factually correct and addresses the question."))

    async def grade(self, case: Case, resp: Response, ctx: GraderContext) -> Verdict:
        if not ctx.judge_provider or not ctx.judge_model:
            raise ValueError("llm_judge requires judge.model in anchor.yaml")
        prompt = _PROMPT.format(
            input=canonical_json(case.input), expect=canonical_json(case.expect),
            rubric=self.rubric, response=resp.text,
        )
        prompt_hash = short_hash(prompt.replace(resp.text, "<response>"))
        key = judge_cache_key(ctx.judge_model, prompt_hash, case_hash(case), short_hash(resp.text))
        if ctx.judge_cache:
            cached = ctx.judge_cache.get(key)
            if cached:
                return cached.model_copy(update={"grader": self.kind})
        judged = await ctx.judge_provider.generate(Request(
            model=ctx.judge_model, messages=[Message(role="user", content=prompt)], params={"temperature": 0}
        ))
        if judged.error:
            return Verdict(grader=self.kind, score=0.0, passed=False, error=judged.error.message)
        try:
            data = json.loads(judged.text)
            score = max(0.0, min(1.0, float(data["score"])))
            verdict = Verdict(grader=self.kind, score=score, passed=bool(data["passed"]), rationale=str(data.get("rationale", "")))
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            return Verdict(grader=self.kind, score=0.0, passed=False, error=f"invalid judge response: {exc}")
        if ctx.judge_cache:
            ctx.judge_cache.put(key, verdict)
        return verdict
