"""Suite loading: JSONL parsing, comment/blank-line handling, and the loud
failures §4.1's trust invariant depends on (duplicate ids, malformed rows).
"""
from __future__ import annotations

import pytest

from anchor.core.suite import SuiteError, load_suite


def test_load_suite_skips_blank_and_comment_lines(tmp_path):
    (tmp_path / "a.jsonl").write_text(
        '# a comment\n\n{"id": "c1", "input": "hi"}\n   \n', encoding="utf-8"
    )
    cases = load_suite("*.jsonl", tmp_path)
    assert [c.id for c in cases] == ["c1"]


def test_load_suite_preserves_file_and_line_order(tmp_path):
    (tmp_path / "a.jsonl").write_text(
        '{"id": "c1", "input": "1"}\n{"id": "c2", "input": "2"}\n', encoding="utf-8"
    )
    (tmp_path / "b.jsonl").write_text('{"id": "c3", "input": "3"}\n', encoding="utf-8")
    cases = load_suite("*.jsonl", tmp_path)
    assert [c.id for c in cases] == ["c1", "c2", "c3"]


def test_load_suite_rejects_duplicate_ids_across_files(tmp_path):
    (tmp_path / "a.jsonl").write_text('{"id": "c1", "input": "hi"}\n', encoding="utf-8")
    (tmp_path / "b.jsonl").write_text('{"id": "c1", "input": "bye"}\n', encoding="utf-8")
    with pytest.raises(SuiteError, match="duplicate case id"):
        load_suite("*.jsonl", tmp_path)


def test_load_suite_rejects_malformed_json(tmp_path):
    (tmp_path / "a.jsonl").write_text("not json\n", encoding="utf-8")
    with pytest.raises(SuiteError, match="invalid JSON"):
        load_suite("*.jsonl", tmp_path)


def test_load_suite_rejects_schema_violation(tmp_path):
    (tmp_path / "a.jsonl").write_text('{"input": "missing the id field"}\n', encoding="utf-8")
    with pytest.raises(SuiteError, match="invalid case"):
        load_suite("*.jsonl", tmp_path)


def test_load_suite_no_matches_raises(tmp_path):
    with pytest.raises(SuiteError, match="no case files matched"):
        load_suite("*.jsonl", tmp_path)
