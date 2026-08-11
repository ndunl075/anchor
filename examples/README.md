# Quickstart suite

10 cases exercising the three P1 graders (`exact`, `contains`, `regex`) across
math/factual/reasoning/format tags — enough to see a per-tag breakdown, not
enough to cost you anything running it twice.

```
cd examples
export ANTHROPIC_API_KEY=...   # or set up an [openai] provider in anchor.yaml
anchor run
anchor runs list
```

This suite is also exercised in CI against a stub provider
(`tests/test_examples.py`) — no live network calls, per ARCHITECTURE.md §11.
