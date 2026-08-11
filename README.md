# anchor

Replay your own prompts against any model. Private score, not a public leaderboard.

Build spec and design decisions live in [ARCHITECTURE.md](ARCHITECTURE.md) — read that first.

Status: **P1 + P2 done.** `anchor init/run/runs/cases` plus the response cache,
`anchor compare` (full regression classification, exit code 2), and `runs bless` all work
against Anthropic and OpenAI. No judge, baseline-diff mode, or bootstrap CIs yet — that's P3/P4.

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
