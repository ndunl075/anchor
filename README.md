<p align="center">
  <img src="anchor/assets/anchor-logo.png" alt="Anchor logo" width="220">
</p>

# anchor

Replay your own prompts against any model. Private score, not a public leaderboard.

Build spec and design decisions live in [ARCHITECTURE.md](ARCHITECTURE.md) — read that first.

Status: **P1 through P5 done.** Anchor supports local suites, immutable replay records,
response caching, full regression comparison, blessed baselines, traffic imports, configurable
redaction, pinned/cached LLM judging, and zero-label pairwise baseline runs. Bootstrap CIs,
paired bootstrap confidence intervals, judge calibration checks, cost estimates, and structured graders.

## Try it locally (no API key)

```sh
npm run setup   # pip install -e ".[dev]"
npm run dev     # stub-run examples → HTML report → opens http://127.0.0.1:8765
```

Or the same without npm: `pip install -e ".[dev]" && python scripts/dev.py`

## 60-second quickstart

~~~sh
pip install replayharness
anchor init my-evals && cd my-evals
anchor import prod.jsonl --map input=.messages --map id=.request_id
export ANTHROPIC_API_KEY=...
anchor run --suite cases/imported-prod.jsonl --name before
anchor runs bless @latest
anchor run --suite cases/imported-prod.jsonl --model claude-opus-5 --baseline --name candidate
anchor compare @baseline @latest
anchor report @baseline @latest --html anchor-report.html
~~~

Everything stays on disk except requests to the model provider you configure. The HTML report is a
single offline file with embedded run data.

For Ollama, vLLM, OpenRouter, or another Chat Completions-compatible endpoint:

~~~yaml
model: local:llama3.2
providers:
  local: { kind: openai_compat, base_url: http://localhost:11434/v1 }
~~~

See [CI usage](docs/ci.md) and [provider plugins](docs/provider-plugins.md).

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
