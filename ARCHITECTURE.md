# Anchor — Architecture

Replay your own prompts against any model. Private score, not a public leaderboard.

This doc is the build spec. Agents: read this fully before writing code. Keep it updated when
decisions change; it is the source of truth over any prior chat context.

---

## 1. Problem & scope

**Job:** a user has real prompts from their own product. A new model ships. They want to know, in
minutes, *does it get better or worse on my traffic* — without uploading anything.

**Core loop:** `suite of cases` → `run against model` → `immutable run record` → `compare two runs`
→ `list of regressions`.

**The headline number is not the product. The regression list is.** A 2% score delta is noise; "these
7 cases went pass→fail" is actionable. Design every surface around that.

### Non-goals
- Public/shared leaderboards, hosted service, accounts, telemetry.
- General agent-trajectory eval (multi-turn tool loops). v1 = single request/response, incl. tool calls
  in the *response*, but no loop execution. Leave a seam (§5.2), don't build it.
- Training, fine-tuning, dataset generation.
- Being promptfoo. Promptfoo is prompt A/B testing. Anchor is **model regression testing over frozen
  cases** — the axis of variation is the *model*, not the prompt.

### Differentiators (protect these)
1. **Labels optional.** Baseline-diff mode (§7.3) lets you eval with zero golden answers.
2. **Replay is first-class.** Runs are immutable, content-addressed, and diffable months apart.
3. **Local-only.** No network except to the model providers you configure.
4. **Cost/latency are results**, not footnotes — a model that's 3% better and 5x the price is a loss.

---

## 2. Stack

| Decision | Choice | Why |
|---|---|---|
| Language | Python 3.10+ | Provider SDKs, eval-adjacent audience, `uvx anchor` install |
| CLI | `typer` + `rich` | Low ceremony, good help output, progress/tables free |
| Config | YAML (`anchor.yaml`) | Users hand-edit it |
| Data | JSONL everywhere | Streamable, greppable, git-diffable, no DB |
| Concurrency | `asyncio` + semaphore | Providers are IO-bound; one model of concurrency only |
| Validation | `pydantic` v2 | Schemas double as docs and JSON Schema export |
| HTTP | `httpx` | One client, async, per-provider retry/timeouts |
| Stats | `numpy` only | Bootstrap CI is ~10 lines; don't pull scipy |
| Tests | `pytest` + recorded fixtures | Zero live calls in CI |
| License | MIT | Maximum adoption |

Hard rules: no telemetry, no analytics, no auto-update check. Secrets from env only — never read from
or written to `anchor.yaml` or run records. Zero required deps beyond the above.

---

## 3. Repo layout

```
anchor/
  cli/            # typer commands, thin — parse, call core, render
    main.py  init.py  run.py  compare.py  report.py  import_.py  cases.py
  core/
    models.py     # pydantic: Case, Request, Response, Verdict, RunManifest, Result
    suite.py      # load/validate/hash suites & cases
    runner.py     # async execution, concurrency, retries, progress
    cache.py      # content-addressed response cache
    scoring.py    # aggregate verdicts -> case/suite scores
    compare.py    # paired diff, bootstrap CI, regression classification
    cost.py       # token -> usd via pricing table
    redact.py     # regex/callable scrubbers applied pre-persist
  providers/
    base.py       # Provider protocol + shared retry/backoff
    anthropic.py  openai.py  openai_compat.py  # (ollama, vllm, together, openrouter)
    registry.py   # name -> class, plus entry_points discovery
  graders/
    base.py       # Grader protocol, GraderSpec
    exact.py  contains.py  regex.py  json_schema.py  numeric.py
    python_fn.py  # user code: file.py::fn
    llm_judge.py  # rubric judge, pinned judge model
    pairwise.py   # baseline-diff judge (§7.3)
    registry.py
  importers/
    jsonl.py  openai_log.py  csv_.py
  report/
    html.py       # single-file, no CDN, embedded JSON
    terminal.py
  pricing.toml    # model -> $/Mtok in|out|cache; user-overridable
tests/
  fixtures/       # recorded provider responses
docs/
examples/         # a real 30-case suite users can run immediately
```

User's project dir after `anchor init`:

```
anchor.yaml
cases/            # *.jsonl
.anchor/
  runs/<run_id>/  manifest.json  results.jsonl
  cache/<hash>.json
  baselines/      # symlinks/pointers to blessed run_ids
```

`.anchor/cache` is gitignored. `.anchor/runs` is **not** — runs are the artifact worth committing.

---

## 4. Data model

All models pydantic. `id` fields are user-facing strings; `*_hash` are sha256, first 16 hex chars.

### 4.1 Case

```python
class Case(BaseModel):
    id: str                      # stable, unique in suite. Never auto-renumber.
    input: str | list[Message]   # str = single user turn
    system: str | None = None
    expect: Any = None           # grader-specific; None is legal (see §7.3)
    graders: list[GraderSpec] = []   # empty -> inherit suite default
    tags: list[str] = []
    params: dict = {}            # per-case overrides: max_tokens, tools, temperature
    weight: float = 1.0
```

`case_hash = sha256(canonical_json(input, system, expect, graders, params))`.
Excludes `id`, `tags`, `weight` — those are metadata; changing them must not invalidate history.

**Invariant:** comparing two results with different `case_hash` is an error, surfaced as
`CHANGED` in the diff, never silently scored. This is what makes replay trustworthy.

### 4.2 Request / Response (provider boundary)

```python
class Request(BaseModel):
    model: str
    messages: list[Message]
    system: str | None
    params: dict            # temperature, max_tokens, top_p, stop, tools, tool_choice
    
class Response(BaseModel):
    text: str
    tool_calls: list[ToolCall] = []
    finish_reason: str
    usage: Usage            # in, out, cache_read, cache_write, reasoning
    latency_ms: int
    model_resolved: str     # what the API actually says it served
    raw: dict               # provider payload, minus auth headers
    error: ErrorInfo | None = None
```

Adapters normalize; they never grade, never retry policy-decide (that's `base.py`), never print.

### 4.3 Result (one row of results.jsonl)

```python
class Result(BaseModel):
    case_id: str
    case_hash: str
    repeat: int             # 0..n-1
    response: Response | None
    verdicts: list[Verdict]
    score: float            # combined, 0..1
    passed: bool
    cost_usd: float         # generation + judge
    cached: bool
    status: Literal["ok","provider_error","grader_error","skipped"]
```

### 4.4 RunManifest (manifest.json)

Everything needed to reproduce or invalidate a run:

```
run_id (ts-slug)  created_at  anchor_version
suite_hash  case_count  case_hashes{id: hash}
provider  model  model_resolved  params  repeats  seed
grader_versions{}  judge_model  judge_prompt_hash
totals{score, pass_rate, cost_usd, p50_latency, p95_latency, tokens_in, tokens_out}
env{python, os}  git{commit, dirty}   # if in a repo
notes  tags
```

`suite_hash` = sha256 of sorted `case_hashes`. Two runs with equal `suite_hash` are directly
comparable; unequal means partial comparison over the intersection, loudly reported.

---

## 5. Component contracts

### 5.1 Provider

```python
class Provider(Protocol):
    name: str
    version: str
    async def generate(self, req: Request) -> Response: ...
    def supports(self, feature: str) -> bool: ...   # "tools","system","json_mode","cache"
```

- Registered by entry point `anchor.providers`, so third parties ship providers as separate packages.
- Retries live in `base.py`: exponential backoff + jitter on 429/5xx/timeouts, `max_retries=3`,
  respect `Retry-After`. Retries **do not** count as repeats and do not multiply cost accounting.
- On terminal failure return `Response(error=...)`; **never raise into the runner**. A dead case
  scores 0 with `status=provider_error` and is excluded from score-delta stats but listed separately.
  Silently scoring errors as 0 would make an outage look like a quality regression.

### 5.2 Seam for agent/multi-turn (do not build in v1)

`Provider.generate` takes one `Request`. Later, a `Runner` strategy can wrap N calls into one
`Response` with a `trajectory` field. Keep `Result.response` typed as an interface, not a struct,
so that lands additively.

### 5.3 Grader

```python
class GraderSpec(BaseModel):
    kind: str
    required: bool = True    # a failed required grader fails the case
    weight: float = 1.0
    config: dict = {}

class Verdict(BaseModel):
    grader: str; score: float; passed: bool
    rationale: str = ""; cost_usd: float = 0.0; error: str | None = None

class Grader(Protocol):
    kind: str; version: str
    async def grade(self, case: Case, resp: Response, ctx: Ctx) -> Verdict: ...
```

Graders are pure w.r.t. their inputs, must be deterministic given `(case, resp)` — except judges,
which must therefore be **cached and pinned** (§6.3). Bump `version` on any behavior change; it lands
in the manifest so old runs stay interpretable.

Built-ins: `exact`, `contains` (any/all/none), `regex`, `json_schema`, `json_path` (extract then
compare), `numeric` (abs/rel tolerance), `latency`, `cost`, `tool_call` (name + arg match),
`python_fn`, `llm_judge`, `pairwise`.

---

## 6. Execution

### 6.1 Runner

```
load suite -> validate -> expand (case × repeats) -> asyncio.Semaphore(concurrency)
  -> cache lookup -> provider.generate -> graders (parallel per case) -> stream Result to jsonl
```

- Results stream to disk as they complete; a killed run is resumable (`anchor run --resume <run_id>`
  skips case_ids already present).
- Progress via `rich`: completed/total, running cost, running pass rate, ETA.
- Ordering in `results.jsonl` is arrival order; readers sort by `(case_id, repeat)`.
- Default `concurrency: 8`. Adaptive backoff drops it on sustained 429s.

### 6.2 Response cache

Key = `sha256(provider, model, canonical(params), canonical(messages), provider.version)`.
Hit ⇒ zero cost, `cached=true`. `temperature > 0` still caches (that's the point of replay) but
`repeat` is part of the key so N repeats stay distinct. `--no-cache` bypasses; `--refresh` overwrites.

### 6.3 Judge discipline

The judge is a measuring instrument; if it drifts, every historical number is wrong.
- `judge_model` and `judge_prompt_hash` are pinned in `anchor.yaml` and recorded in the manifest.
- Judge calls are cached on `(judge_model, prompt_hash, case_hash, response_text_hash)`.
- Judge temperature forced to 0.
- Comparing runs with different judge pins ⇒ warning banner in every output.
- `anchor judge-check` — run the judge against a small human-labeled calibration set; reports
  agreement rate. Ship this in v1; it's the credibility feature and nobody else does it well.

### 6.4 Cost

`pricing.toml` maps model → `$/Mtok`, with `[overrides]` in `anchor.yaml`. Unknown model ⇒ cost
reported as `null`, never guessed. `anchor run --dry-run` estimates cost from token-counted inputs
plus `max_tokens` ceiling, and exits.

---

## 7. Scoring & comparison

### 7.1 Aggregation

```
case_score   = weighted mean of verdict scores   (combine: mean | min | all — default mean)
case_passed  = all(required verdicts passed)
case_final   = mean over repeats                 (also keep stdev)
suite_score  = weight-normalized mean over cases
pass_rate    = mean(case_passed) over case×repeat
```

Also emit per-tag breakdowns — "worse at extraction, better at summarization" is the insight users
actually act on.

### 7.2 Compare

`anchor compare <run_a> <run_b>` classifies each case:

| Class | Meaning |
|---|---|
| `REGRESSION` | passed in A, failed in B |
| `FIX` | failed in A, passed in B |
| `DRIFT` | both pass, \|Δscore\| > threshold (default 0.15) |
| `STABLE` | no material change |
| `ERROR` | provider/grader failure in either |
| `CHANGED` | `case_hash` differs — not comparable |
| `MISSING` | present in one run only |

Output order: REGRESSION first, always. Then ERROR, FIX, DRIFT. Headline block shows Δscore with CI,
Δcost, Δp95 latency, and counts — never Δscore alone.

### 7.3 Baseline-diff mode (no golden answers)

For imported real traffic with `expect: null`. Grade `pairwise`: judge sees the case input, the
**baseline run's** response for that case, and the candidate response, blind and order-randomized
(run both orders, disagreement ⇒ tie). Score ∈ {0, 0.5, 1} = lose/tie/win. Suite metric = win rate
vs. baseline with CI.

This is the fastest path to value: `anchor import prod.jsonl && anchor run --baseline`. Make the
docs lead with it.

### 7.4 Statistics — don't oversell deltas

- Paired bootstrap over cases (10k resamples, seeded) → 95% CI on Δsuite_score and on win rate.
- With repeats > 1, resample cases (not repeats) — cases are the independent unit.
- Print CI next to every delta. If the CI crosses 0, label it `not significant` in plain words.
- Warn when `case_count < 30` that CIs are wide and the regression list matters more.
- Never report more than 1 decimal place of a percentage.

---

## 8. CLI surface

```
anchor init                      scaffold anchor.yaml + cases/ + example case
anchor cases add                 append a case interactively
anchor cases list|validate       validate = hash check + grader/provider resolution, no network
anchor import <file>             --format jsonl|openai|csv --map input=.messages --limit N --sample N
anchor run                       --model M --suite S --repeats N --concurrency C --tags T
                                 --dry-run --no-cache --resume RUN --baseline --name NOTE
anchor compare <a> <b>           --format term|json|md  --threshold 0.15  --only regression
anchor report <run...>           --html out.html   (single file, embedded data, no CDN)
anchor runs list|show|bless      bless <run> <name> -> .anchor/baselines/<name>
anchor judge-check               judge agreement vs. calibration set
```

Run refs accept: `run_id`, `@latest`, `@baseline`, `@baseline:<name>`, `-1` (nth most recent).

Exit codes: `0` ok, `1` usage/config error, `2` regressions found (so it drops into CI unmodified),
`3` provider errors exceeded threshold.

---

## 9. Config

```yaml
version: 1
suite: cases/*.jsonl

model: claude-opus-5          # default target
providers:
  anthropic: { api_key_env: ANTHROPIC_API_KEY }
  local:     { kind: openai_compat, base_url: http://localhost:11434/v1 }

params: { temperature: 0, max_tokens: 1024 }
repeats: 1
concurrency: 8

graders:                       # default graders when a case declares none
  - kind: llm_judge
    config: { rubric: "Answer is factually correct and addresses the question." }

judge:
  model: claude-opus-5         # pinned; changing this invalidates comparability
  temperature: 0

compare: { drift_threshold: 0.15, fail_on_regression: true }
redact:
  - pattern: '\b[\w.+-]+@[\w-]+\.[\w.]+\b'
    replace: '<email>'
```

---

## 10. Build order

Each phase ends shippable and demoable.

**P1 — walking skeleton.** models.py, suite load+hash, anthropic + openai providers, `exact`/
`contains`/`regex` graders, runner with concurrency, `run`, `runs list`, terminal output, JSONL
persistence. Demo: score a 10-case suite.

**P2 — replay.** cache, `compare` with the full class table, `@latest`/`@baseline`, `bless`,
exit code 2, per-tag breakdown. Demo: regression list between two models.

**P3 — real traffic.** `import` + mappers, `llm_judge`, `pairwise` + `--baseline`, redaction.
Demo: zero-label eval on production logs.

**P4 — trust.** bootstrap CIs, `judge-check` + calibration set, `--dry-run` cost, `python_fn`,
`json_schema`/`json_path`/`tool_call` graders, `--resume`.

**P5 — polish for launch.** single-file HTML report, `openai_compat` (ollama/vllm/openrouter),
entry-point plugin docs, examples/ suite, GitHub Action snippet, README with the 60-second quickstart
(import → run → compare).

---

## 11. Testing

- **No live API calls in CI.** Providers tested against recorded fixtures; a `record` mode refreshes
  them behind an env flag.
- Golden tests on hashing: `case_hash` must be stable across Python versions and dict ordering.
  This is the one bug that silently destroys the product's value — cover it hard.
- Property tests on `compare` classification (every case lands in exactly one class).
- Seeded bootstrap must be reproducible bit-for-bit.
- `examples/` suite runs in CI against a stub provider.

---

## 12. Open decisions

- Package/CLI name — `anchor` is taken on PyPI. Candidates: `anchor-eval`, `replayharness`. CLI
  stays `anchor`. **Resolve before P1 publishes.**
- Whether `.anchor/runs` should be committed by default, or opt-in via `anchor init --track-runs`.
- Streaming responses: not needed for eval; add only if latency-to-first-token becomes a metric.
- Multi-turn/agent trajectories — deferred, seam noted in §5.2.
