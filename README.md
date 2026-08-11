# anchor

Replay your own prompts against any model. Private score, not a public leaderboard.

Build spec and design decisions live in [ARCHITECTURE.md](ARCHITECTURE.md) — read that first.

Status: **P1 walking skeleton, done.** `anchor init`, `anchor run`, `anchor runs list/show`,
`anchor cases list/validate` all work against Anthropic and OpenAI. No caching, compare, or
judge yet — that's P2+.

```
pip install -e ".[dev]"
cd examples
export ANTHROPIC_API_KEY=...
anchor run
anchor runs list
```

Run the test suite (no live network calls):

```
pytest
```
