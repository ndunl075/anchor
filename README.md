# anchor

Replay your own prompts against any model. Private score, not a public leaderboard.

Build spec and design decisions live in [ARCHITECTURE.md](ARCHITECTURE.md) — read that first.

Status: **P1 + P2 + P3 done.** Anchor supports local suites, immutable replay records,
response caching, full regression comparison, blessed baselines, traffic imports, configurable
redaction, pinned/cached LLM judging, and zero-label pairwise baseline runs. Bootstrap CIs,
calibration checks, and cost estimates land in P4.

```
pip install -e ".[dev]"
cd examples
export ANTHROPIC_API_KEY=...
anchor run --name before
# ... change something, e.g. try a different --model ...
anchor run --name after
anchor compare -- -2 -1
```

Run the test suite (no live network calls):

```
pytest
```

For zero-label production traffic, import it locally, bless a reference run, then judge a
candidate against it:

```
anchor import prod.jsonl --map input=.messages --map id=.request_id
anchor run --suite cases/imported-prod.jsonl --name baseline
anchor runs bless @latest
anchor run --suite cases/imported-prod.jsonl --model gpt-5 --baseline
```
