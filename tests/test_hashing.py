"""Golden tests on hashing (§11): "case_hash must be stable across Python
versions and dict ordering. This is the one bug that silently destroys the
product's value — cover it hard."
"""
from __future__ import annotations

from anchor.core.models import Case
from anchor.core.suite import canonical_json, case_hash, suite_hash


def test_case_hash_stable_across_dict_key_order():
    c1 = Case(id="a", input="hi", expect="ok", params={"temperature": 0, "max_tokens": 10})
    c2 = Case(id="a", input="hi", expect="ok", params={"max_tokens": 10, "temperature": 0})
    assert case_hash(c1) == case_hash(c2)


def test_case_hash_excludes_id_tags_and_weight():
    """id/tags/weight are metadata (§4.1) — changing them must not invalidate history."""
    c1 = Case(id="a", input="hi", expect="ok", tags=["x"], weight=2.0)
    c2 = Case(id="b", input="hi", expect="ok", tags=["y"], weight=5.0)
    assert case_hash(c1) == case_hash(c2)


def test_case_hash_changes_with_input():
    c1 = Case(id="a", input="hi")
    c2 = Case(id="a", input="bye")
    assert case_hash(c1) != case_hash(c2)


def test_case_hash_changes_with_expect():
    c1 = Case(id="a", input="hi", expect="4")
    c2 = Case(id="a", input="hi", expect="5")
    assert case_hash(c1) != case_hash(c2)


def test_case_hash_is_16_lowercase_hex_chars():
    h = case_hash(Case(id="a", input="hi"))
    assert len(h) == 16
    int(h, 16)  # raises ValueError if not valid hex


def test_canonical_json_sorts_keys_and_is_deterministic():
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})
    assert canonical_json({"a": 2, "b": 1}) == '{"a":2,"b":1}'


def test_suite_hash_is_order_independent():
    hashes = {"c1": "aaaaaaaaaaaaaaaa", "c2": "bbbbbbbbbbbbbbbb"}
    reordered = {"c2": "bbbbbbbbbbbbbbbb", "c1": "aaaaaaaaaaaaaaaa"}
    assert suite_hash(hashes) == suite_hash(reordered)


def test_suite_hash_changes_if_any_case_hash_changes():
    a = {"c1": "aaaaaaaaaaaaaaaa", "c2": "bbbbbbbbbbbbbbbb"}
    b = {"c1": "aaaaaaaaaaaaaaaa", "c2": "cccccccccccccccc"}
    assert suite_hash(a) != suite_hash(b)
