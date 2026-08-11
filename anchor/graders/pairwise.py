"""Blind pairwise baseline judge for zero-label traffic evaluation (§7.3)."""
from __future__ import annotations

import json

from anchor.core.judge_cache import judge_cache_key
from anchor.core.models import Case, Message, Request, Response, Verdict
from anchor.core.suite import case_hash, canonical_json, short_hash
from anchor.graders.base import GraderContext

_PROMPT = """You are evaluating two answers to the same user request. Decide which answer is better.
Return only JSON with winner ("A", "B", or "tie") and rationale (brief string).
User case: {input}
Answer A: {first}
Answer B: {second}"""


class PairwiseGrader:
    kind = "pairwise"
    version = "1"

    def __init__(self, config: dict):
        self.config = config

    async def grade(self, case: Case, resp: Response, ctx: GraderContext) -> Verdict:
        baseline = ctx.baseline_responses.get((case.id, ctx.repeat))
        if baseline is None:
            raise ValueError(f"no baseline response for {case.id!r} repeat {ctx.repeat}")
        if not ctx.judge_provider or not ctx.judge_model:
            raise ValueError("pairwise requires judge.model in anchor.yaml")

        # Run both orders. A disagreement is explicitly a tie (§7.3), removing
        # position bias without relying on a non-reproducible random order.
        prompt = _PROMPT.format(input=canonical_json(case.input), first=baseline.text, second=resp.text)
        prompt_hash = short_hash(_PROMPT)
        response_hash = short_hash(canonical_json({"baseline": baseline.text, "candidate": resp.text}))
        key = judge_cache_key(ctx.judge_model, prompt_hash, case_hash(case), response_hash)
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
            first_result = json.loads(judged.text)
            first_winner = str(first_result["winner"]).lower()
            reversed_prompt = _PROMPT.format(input=canonical_json(case.input), first=resp.text, second=baseline.text)
            reversed_judged = await ctx.judge_provider.generate(Request(
                model=ctx.judge_model, messages=[Message(role="user", content=reversed_prompt)], params={"temperature": 0}
            ))
            if reversed_judged.error:
                return Verdict(grader=self.kind, score=0.0, passed=False, error=reversed_judged.error.message)
            second_result = json.loads(reversed_judged.text)
            second_winner = str(second_result["winner"]).lower()
            # First order: B is candidate. Reversed order: A is candidate.
            first_choice = "candidate" if first_winner == "b" else ("baseline" if first_winner == "a" else "tie")
            second_choice = "candidate" if second_winner == "a" else ("baseline" if second_winner == "b" else "tie")
            choice = first_choice if first_choice == second_choice else "tie"
            score = {"baseline": 0.0, "tie": 0.5, "candidate": 1.0}[choice]
            verdict = Verdict(grader=self.kind, score=score, passed=score >= 0.5, rationale=str(first_result.get("rationale", "")))
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            return Verdict(grader=self.kind, score=0.0, passed=False, error=f"invalid pairwise judge response: {exc}")
        if ctx.judge_cache:
            ctx.judge_cache.put(key, verdict)
        return verdict
