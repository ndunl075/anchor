"""Single-file, offline HTML evaluation dossier (P5).

Visual language borrows Opennote's notebook feel: cream paper, serif display,
soft magenta banner, ruled-paper results — still zero CDN / fully offline.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
from anchor.core.models import Result, RunManifest

_LOGO_PATH = Path(__file__).parents[1] / "assets" / "anchor-logo.png"


def _logo_data_uri() -> str:
    if not _LOGO_PATH.exists():
        return ""
    return "data:image/png;base64," + base64.b64encode(_LOGO_PATH.read_bytes()).decode("ascii")


def render_html(manifests: list[RunManifest], results_by_run: dict[str, list[Result]]) -> str:
    data = {
        "runs": [
            {
                "id": m.run_id,
                "model": f"{m.provider}:{m.model}",
                "created_at": m.created_at.isoformat(),
                "score": m.totals.score,
                "pass_rate": m.totals.pass_rate,
                "cost": m.totals.cost_usd,
                "results": [
                    {
                        "case": r.case_id,
                        "score": r.score,
                        "passed": r.passed,
                        "status": r.status,
                        "text": r.response.text if r.response else "",
                    }
                    for r in results_by_run.get(m.run_id, [])
                ],
            }
            for m in manifests
        ]
    }
    logo = _logo_data_uri()
    # Script text does not decode HTML entities, so keep JSON as real quotes and
    # only neutralize sequences that could terminate the script element early.
    payload = (
        json.dumps(data, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    return f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Anchor field report</title>
<style>
:root {{
  --paper: #fbfaf6;
  --paper-deep: #f3f0e8;
  --ink: #0a0a0a;
  --mute: #5c5a55;
  --line: rgba(25, 25, 25, 0.12);
  --rule: #d7e4f2;
  --banner: #f7c3f7;
  --banner-ink: #9d17a0;
  --good: #1f7a4c;
  --bad: #c23b2a;
  --chip: #fff;
  --display: "Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif;
  --sans: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono: "JetBrains Mono", ui-monospace, "SF Mono", Consolas, monospace;
}}
* {{ box-sizing: border-box; }}
html {{ scroll-behavior: smooth; }}
body {{
  margin: 0;
  color: var(--ink);
  background:
    radial-gradient(circle at 12% -10%, rgba(247, 195, 247, 0.35), transparent 42%),
    radial-gradient(circle at 88% 8%, rgba(215, 228, 242, 0.55), transparent 38%),
    var(--paper);
  font: 16px/1.55 var(--sans);
  -webkit-font-smoothing: antialiased;
}}
.banner {{
  background: var(--banner);
  color: var(--banner-ink);
  text-align: center;
  padding: 10px 18px;
  font-size: 14px;
  letter-spacing: 0.01em;
}}
.banner strong {{ font-weight: 600; }}
.shell {{ max-width: 1080px; margin: 0 auto; padding: 28px 24px 80px; }}
.topnav {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 48px;
  animation: rise 0.7s ease both;
}}
.brand {{
  display: flex;
  align-items: center;
  gap: 12px;
  text-decoration: none;
  color: inherit;
}}
.brand img {{
  width: 42px;
  height: 42px;
  border-radius: 50%;
  border: 1px solid var(--line);
  background: #fff;
}}
.brand-name {{
  font-family: var(--display);
  font-size: 28px;
  line-height: 1;
  letter-spacing: -0.02em;
}}
.stamp {{
  color: var(--mute);
  font-size: 13px;
  border: 1px solid rgba(25, 25, 25, 0.2);
  border-radius: 10px;
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.55);
}}
.hero {{
  text-align: center;
  padding: 12px 0 40px;
  animation: rise 0.8s ease 0.08s both;
}}
.kicker {{
  display: inline-block;
  color: var(--banner-ink);
  font-size: 13px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 14px;
}}
.kicker::after {{
  content: "";
  display: block;
  width: 42%;
  margin: 8px auto 0;
  border-bottom: 2px solid var(--ink);
  transform: rotate(-1.5deg);
  opacity: 0.85;
}}
h1 {{
  margin: 0 auto 14px;
  max-width: 14ch;
  font: 400 clamp(42px, 7vw, 72px)/1.05 var(--display);
  letter-spacing: -0.03em;
}}
.lede {{
  margin: 0 auto;
  max-width: 42ch;
  color: var(--mute);
  font-size: 17px;
}}
#metrics {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
  margin: 8px 0 44px;
  animation: rise 0.85s ease 0.16s both;
}}
.metric {{
  background: linear-gradient(180deg, #fff 0%, var(--paper-deep) 100%);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 22px 20px;
  min-height: 128px;
  box-shadow: 0 1px 0 rgba(255,255,255,0.8) inset;
  transition: transform 0.25s ease, box-shadow 0.25s ease;
}}
.metric:hover {{
  transform: translateY(-2px);
  box-shadow: 0 10px 28px rgba(25, 25, 25, 0.06);
}}
.metric label {{
  display: block;
  font-size: 12px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--mute);
  word-break: break-word;
}}
.metric strong {{
  display: block;
  margin-top: 14px;
  font: 400 40px/1 var(--display);
  letter-spacing: -0.03em;
}}
.metric span {{
  display: block;
  margin-top: 10px;
  color: var(--mute);
  font-size: 14px;
}}
.panel {{
  background:
    repeating-linear-gradient(
      transparent,
      transparent 27px,
      var(--rule) 27px,
      var(--rule) 28px
    ),
    #fff;
  border: 1px solid var(--line);
  border-radius: 20px;
  padding: 28px 22px 18px;
  box-shadow: 0 18px 50px rgba(25, 25, 25, 0.05);
  animation: rise 0.9s ease 0.22s both;
}}
.panel-head {{
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 18px;
  padding-bottom: 8px;
}}
.panel-head h2 {{
  margin: 6px 0 0;
  font: 400 34px/1.1 var(--display);
  letter-spacing: -0.02em;
}}
.panel-kicker {{
  color: var(--banner-ink);
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}}
#filter {{
  width: min(100%, 420px);
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(25, 25, 25, 0.2);
  border-radius: 10px;
  padding: 12px 14px;
  color: var(--ink);
  font: 14px/1.3 var(--sans);
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}}
#filter:focus {{
  border-color: var(--banner-ink);
  box-shadow: 0 0 0 3px rgba(247, 195, 247, 0.55);
}}
.table-wrap {{ overflow-x: auto; }}
table {{
  border-collapse: collapse;
  width: 100%;
  margin-top: 8px;
}}
th {{
  font: 600 11px/1 var(--sans);
  color: var(--mute);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  text-align: left;
}}
td, th {{
  padding: 14px 10px;
  border-bottom: 1px solid rgba(25, 25, 25, 0.08);
  vertical-align: top;
}}
tbody tr {{
  transition: background 0.15s ease;
}}
tbody tr:hover {{
  background: rgba(247, 195, 247, 0.14);
}}
.pass {{ color: var(--good); font-weight: 600; }}
.fail {{ color: var(--bad); font-weight: 600; }}
.pill {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  border: 1px solid currentColor;
  background: #fff;
}}
.pill.pass {{ background: rgba(31, 122, 76, 0.08); }}
.pill.fail {{ background: rgba(194, 59, 42, 0.08); }}
code {{
  font: 12.5px/1.45 var(--mono);
  white-space: pre-wrap;
  color: #222;
}}
.score {{
  font-family: var(--display);
  font-size: 18px;
}}
@keyframes rise {{
  from {{ opacity: 0; transform: translateY(12px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}
@media (max-width: 700px) {{
  .shell {{ padding: 20px 16px 64px; }}
  .topnav {{ align-items: start; flex-direction: column; }}
  .panel {{ padding: 22px 14px 10px; border-radius: 16px; }}
  #filter {{ width: 100%; }}
  h1 {{ max-width: none; }}
}}
</style>
<body>
  <div class="banner"><strong>Private model evaluation</strong> · local runs only · OFFLINE ARTIFACT</div>
  <div class="shell">
    <header class="topnav">
      <div class="brand">
        <img src="{logo}" alt="Anchor logo" width="42" height="42">
        <div class="brand-name">Anchor</div>
      </div>
      <div class="stamp" id="stamp"></div>
    </header>

    <section class="hero">
      <div class="kicker">private model evaluation</div>
      <h1>Anchor</h1>
      <p class="lede">Field report for frozen runs — scores, failures, and responses in one offline notebook.</p>
    </section>

    <div id="metrics"></div>

    <section class="panel">
      <div class="panel-head">
        <div>
          <div class="panel-kicker">frozen runs</div>
          <h2>Results, case by case</h2>
        </div>
        <input id="filter" placeholder="Filter cases, models, or response text…">
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>run / model</th>
              <th>case</th>
              <th>verdict</th>
              <th>score</th>
              <th>response</th>
            </tr>
          </thead>
          <tbody id="rows"></tbody>
        </table>
      </div>
    </section>
  </div>
<script id="anchor-data" type="application/json">{payload}</script>
<script>
const data = JSON.parse(document.querySelector('#anchor-data').textContent);
const runs = data.runs;
const pct = n => (n * 100).toFixed(1) + '%';
const money = n => '$' + n.toFixed(4);
document.querySelector('#stamp').textContent =
  runs.length + ' FROZEN RUN' + (runs.length === 1 ? '' : 'S') + ' · OFFLINE ARTIFACT';
document.querySelector('#metrics').innerHTML = runs.map(r =>
  '<article class="metric"><label>' + r.model + '</label><strong>' + pct(r.score) +
  '</strong><span>pass ' + pct(r.pass_rate) + ' · ' + money(r.cost) + '</span></article>'
).join('');
const render = () => {{
  const q = document.querySelector('#filter').value.toLowerCase();
  document.querySelector('#rows').innerHTML = runs.flatMap(r => r.results.map(x => {{
    const s = (r.id + ' ' + r.model + ' ' + x.case + ' ' + x.text).toLowerCase();
    if (!s.includes(q)) return '';
    const cls = x.passed ? 'pass' : 'fail';
    const label = x.status + ' / ' + (x.passed ? 'pass' : 'fail');
    return '<tr><td><code>' + r.id + '<br>' + r.model + '</code></td><td><code>' + x.case +
      '</code></td><td><span class="pill ' + cls + '">' + label + '</span></td><td class="score">' +
      pct(x.score) + '</td><td><code>' + x.text.replaceAll('&','&amp;').replaceAll('<','&lt;') +
      '</code></td></tr>';
  }})).join('');
}};
document.querySelector('#filter').oninput = render;
render();
</script>
</body>
</html>
"""


def write_html(path: Path, manifests: list[RunManifest], results_by_run: dict[str, list[Result]]) -> None:
    path.write_text(render_html(manifests, results_by_run), encoding="utf-8")
