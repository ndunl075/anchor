"""P3 real-traffic primitives stay local, redacted, and deterministic."""
from __future__ import annotations

import json

from typer.testing import CliRunner

from anchor.cli.main import app
from anchor.core.config import RedactRule
from anchor.core.redact import redact_value
from anchor.importers.common import case_from_record


def test_redaction_recurses_without_mutating_source():
    original = {"text": "mail nico@example.com", "items": ["nico@example.com"]}
    redacted = redact_value(original, [RedactRule(pattern=r"[\w.+-]+@[\w-]+\.[\w.]+", replace="<email>")])
    assert redacted == {"text": "mail <email>", "items": ["<email>"]}
    assert original["text"] == "mail nico@example.com"


def test_import_mapper_prefers_source_id_and_scrubs_input():
    case = case_from_record(
        {"request_id": "r-1", "messages": [{"role": "user", "content": "email nico@example.com"}]},
        0,
        {"id": ".request_id", "input": ".messages"},
        [RedactRule(pattern=r"[\w.+-]+@[\w-]+\.[\w.]+", replace="<email>")],
    )
    assert case.id == "r-1"
    assert case.input[0].content == "email <email>"
    assert case.expect is None


def test_import_command_writes_frozen_cases(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(app, ["init", "."]).exit_code == 0
    (tmp_path / "traffic.jsonl").write_text(json.dumps({"id": "a", "input": "hello"}) + "\n", encoding="utf-8")
    result = runner.invoke(app, ["import", "traffic.jsonl"])
    assert result.exit_code == 0, result.output
    imported = (tmp_path / "cases" / "imported-traffic.jsonl").read_text(encoding="utf-8")
    assert json.loads(imported)["expect"] is None
