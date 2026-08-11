from pathlib import Path
import json
from anchor.core.models import EnvInfo, Result, RunManifest
from anchor.report.html import render_html


def test_html_report_embeds_data_and_filter():
    manifest = RunManifest(run_id="r1", anchor_version="x", suite_hash="s", case_count=1,
        provider="stub", model="m", env=EnvInfo(python="3", os="x"))
    html = render_html([manifest], {"r1": [Result(case_id="c1", case_hash="h", response=None)]})
    assert "OFFLINE ARTIFACT" in html
    assert "anchor-data" in html
    assert "data:image/png;base64," in html
    assert "c1" in html
    # Script text does not decode HTML entities — payload must stay parseable JSON.
    assert '&quot;' not in html
    start = html.index('id="anchor-data"')
    blob = html[html.index(">", start) + 1 : html.index("</script>", start)]
    data = json.loads(blob)
    assert data["runs"][0]["results"][0]["case"] == "c1"
