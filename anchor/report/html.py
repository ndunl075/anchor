"""Single-file, offline HTML evaluation dossier (P5)."""
from __future__ import annotations

import json
from html import escape
from pathlib import Path
from anchor.core.models import Result, RunManifest


def render_html(manifests: list[RunManifest], results_by_run: dict[str, list[Result]]) -> str:
    data = {"runs": [{"id": m.run_id, "model": f"{m.provider}:{m.model}",
        "created_at": m.created_at.isoformat(), "score": m.totals.score,
        "pass_rate": m.totals.pass_rate, "cost": m.totals.cost_usd,
        "results": [{"case": r.case_id, "score": r.score, "passed": r.passed,
          "status": r.status, "text": r.response.text if r.response else ""}
          for r in results_by_run.get(m.run_id, [])]} for m in manifests]}
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Anchor field report</title><style>
:root{{--ink:#e7e0d4;--muted:#9d978d;--paper:#17191b;--panel:#202428;--line:#393d3e;--acid:#e7cb5b;--bad:#ef7866;--good:#86c69b}}*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at 80% 0,#313328 0,transparent 32rem),var(--paper);color:var(--ink);font:15px/1.45 Georgia,serif}}main{{max-width:1200px;margin:auto;padding:52px 28px}}header{{border-bottom:1px solid var(--line);padding-bottom:24px;display:flex;justify-content:space-between;align-items:end}}h1{{font:700 clamp(36px,7vw,78px)/.9 Georgia,serif;letter-spacing:-.06em;margin:0}}.kicker,.metric label{{font:700 11px/1 ui-monospace,Consolas,monospace;letter-spacing:.13em;text-transform:uppercase;color:var(--acid)}}.stamp{{color:var(--muted);font:12px ui-monospace,Consolas,monospace}}#metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:28px 0}}.metric{{background:var(--panel);border:1px solid var(--line);padding:18px;min-height:110px}}.metric strong{{display:block;font:32px/1 Georgia,serif;margin-top:12px}}section{{margin-top:40px}}h2{{font:700 27px/1 Georgia,serif;margin:0 0 14px}}#filter{{width:100%;background:#111315;border:1px solid var(--line);padding:13px;color:var(--ink);font:14px ui-monospace,Consolas,monospace}}table{{border-collapse:collapse;width:100%;margin-top:14px}}th{{font:10px ui-monospace,Consolas,monospace;color:var(--muted);letter-spacing:.1em;text-transform:uppercase;text-align:left}}td,th{{padding:12px 8px;border-bottom:1px solid var(--line);vertical-align:top}}.pass{{color:var(--good)}}.fail{{color:var(--bad)}}code{{font:12px ui-monospace,Consolas,monospace;white-space:pre-wrap;color:#c4c5bf}}@media(max-width:700px){{#metrics{{grid-template-columns:repeat(2,1fr)}}main{{padding:28px 16px}}header{{display:block}}.stamp{{margin-top:14px}}}}</style>
<main><header><div><div class="kicker">private model evaluation</div><h1>Anchor<br>field report</h1></div><div class="stamp" id="stamp"></div></header><div id="metrics"></div><section><div class="kicker">frozen runs</div><h2>Results, case by case</h2><input id="filter" placeholder="Filter cases, models, or response text…"><table><thead><tr><th>run / model</th><th>case</th><th>verdict</th><th>score</th><th>response</th></tr></thead><tbody id="rows"></tbody></table></section></main>
<script id="anchor-data" type="application/json">{escape(json.dumps(data))}</script><script>
const data=JSON.parse(document.querySelector('#anchor-data').textContent),runs=data.runs,pct=n=>(n*100).toFixed(1)+'%',money=n=>'$'+n.toFixed(4);
document.querySelector('#stamp').textContent=runs.length+' FROZEN RUN'+(runs.length===1?'':'S')+' · OFFLINE ARTIFACT';
document.querySelector('#metrics').innerHTML=runs.map(r=>'<article class="metric"><label>'+r.model+'</label><strong>'+pct(r.score)+'</strong><span>pass '+pct(r.pass_rate)+' · '+money(r.cost)+'</span></article>').join('');
const render=()=>{{const q=document.querySelector('#filter').value.toLowerCase();document.querySelector('#rows').innerHTML=runs.flatMap(r=>r.results.map(x=>{{const s=(r.id+' '+r.model+' '+x.case+' '+x.text).toLowerCase();if(!s.includes(q))return '';return '<tr><td><code>'+r.id+'<br>'+r.model+'</code></td><td><code>'+x.case+'</code></td><td class="'+(x.passed?'pass':'fail')+'">'+x.status+' / '+(x.passed?'pass':'fail')+'</td><td>'+pct(x.score)+'</td><td><code>'+x.text.replaceAll('&','&amp;').replaceAll('<','&lt;')+'</code></td></tr>'}})).join('')}};document.querySelector('#filter').oninput=render;render();
</script>"""


def write_html(path: Path, manifests: list[RunManifest], results_by_run: dict[str, list[Result]]) -> None:
    path.write_text(render_html(manifests, results_by_run), encoding="utf-8")
