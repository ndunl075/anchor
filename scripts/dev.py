#!/usr/bin/env python3
"""Local demo loop — `npm run dev` / `python scripts/dev.py`.

Runs the examples suite against a stub provider (no API key), writes the HTML
report, serves it, and opens a browser. Ctrl+C to stop.
"""
from __future__ import annotations

import argparse
import asyncio
import platform
import secrets
import sys
import time
import webbrowser
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
REPORT = ROOT / "anchor-report.html"
DEFAULT_PORT = 8765

# Keep import path working before editable install, and after.
sys.path.insert(0, str(ROOT))

from anchor import __version__  # noqa: E402
from anchor.core.config import load_config  # noqa: E402
from anchor.core.models import EnvInfo, RunManifest  # noqa: E402
from anchor.core.runner import RunConfig, run_suite  # noqa: E402
from anchor.core.scoring import aggregate_totals  # noqa: E402
from anchor.core.suite import compute_case_hashes, load_suite, suite_hash  # noqa: E402
from anchor.report.html import write_html  # noqa: E402
from tests.fixtures.stub_provider import StubProvider  # noqa: E402

# Canned answers for examples/cases/quickstart.jsonl — same map CI uses.
_BASELINE = {
    "What is 12 * 12? Answer with just the number.": "144",
    "What is the capital of France? Answer with just the city name.": "Paris",
    "Name a primary color.": "Blue is one of the primary colors.",
    "List the first three planets from the sun, comma separated.": "Mercury, Venus, Earth",
    "Describe a cat without using the word 'dog'.": "A cat is a small, independent, furry pet.",
    "Give today's date in YYYY-MM-DD format only.": "2026-08-11",
    "Reply with exactly one word: yes or no. Is water wet?": "yes",
    "What is 2 + 2?": "4",
    "Summarize: 'The quick brown fox jumps over the lazy dog.' Mention the animal that jumps.": "The fox jumps.",
    "What color is the sky on a clear day? One word.": "Blue",
}

# Intentional regressions so the report shows pass→fail rows.
_CANDIDATE = {
    **_BASELINE,
    "What is the capital of France? Answer with just the city name.": "Lyon",
    "Give today's date in YYYY-MM-DD format only.": "08/11/2026",
}


async def _run_once(name: str, model: str, answers: dict[str, str]) -> tuple[RunManifest, list]:
    config = load_config(EXAMPLES / "anchor.yaml")
    cases = load_suite(config.suite, EXAMPLES)
    provider = StubProvider(responses=answers)
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3) + f"-{name}"
    run_dir = EXAMPLES / ".anchor" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    results_path = run_dir / "results.jsonl"

    run_config = RunConfig(model=model, default_graders=config.graders, params=config.params)
    results = await run_suite(cases, provider, run_config, results_path)

    case_hashes = compute_case_hashes(cases)
    manifest = RunManifest(
        run_id=run_id,
        anchor_version=__version__,
        suite_hash=suite_hash(case_hashes),
        case_count=len(cases),
        case_hashes=case_hashes,
        provider="stub",
        model=model,
        model_resolved=model,
        params=run_config.params,
        totals=aggregate_totals(results),
        env=EnvInfo(python=platform.python_version(), os=platform.platform()),
        notes=name,
        created_at=datetime.now(timezone.utc),
    )
    (run_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return manifest, results


def _serve(port: int) -> None:
    handler = partial(SimpleHTTPRequestHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{port}/{REPORT.name}"
    print(f"\n  Anchor report -> {url}")
    print("  Press Ctrl+C to stop.\n")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        server.server_close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Anchor local demo and open the HTML report.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-open", action="store_true", help="Serve only; don't open a browser.")
    parser.add_argument("--build-only", action="store_true", help="Write the report and exit.")
    args = parser.parse_args()

    print("running examples suite (stub provider, no API key)…")
    baseline_m, baseline_r = asyncio.run(_run_once("baseline", "claude-opus-5", _BASELINE))
    candidate_m, candidate_r = asyncio.run(_run_once("candidate", "gpt-5", _CANDIDATE))
    write_html(
        REPORT,
        [baseline_m, candidate_m],
        {baseline_m.run_id: baseline_r, candidate_m.run_id: candidate_r},
    )
    print(f"wrote {REPORT}")
    print(f"  baseline  score={baseline_m.totals.score:.1%}  pass={baseline_m.totals.pass_rate:.1%}")
    print(f"  candidate score={candidate_m.totals.score:.1%}  pass={candidate_m.totals.pass_rate:.1%}")

    if args.build_only:
        return 0

    if args.no_open:
        # Still serve; skip webbrowser by monkeypatching briefly.
        webbrowser.open = lambda *_a, **_k: False  # type: ignore[method-assign]
    _serve(args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
