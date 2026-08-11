"""exact/contains/regex graders (§5.3): behavior and config-validation edges."""
from __future__ import annotations

import pytest

from anchor.core.models import Case, GraderSpec, Response
from anchor.graders.base import GraderContext
from anchor.graders.registry import UnknownGraderError, build_grader

pytestmark = pytest.mark.asyncio
ctx = GraderContext()


async def grade(spec: GraderSpec, case: Case, resp: Response):
    return await build_grader(spec).grade(case, resp, ctx)


async def test_exact_pass_and_fail():
    case = Case(id="c", input="x", expect="4")
    assert (await grade(GraderSpec(kind="exact"), case, Response(text="4"))).passed
    assert not (await grade(GraderSpec(kind="exact"), case, Response(text="5"))).passed


async def test_exact_strip_and_case_config():
    case = Case(id="c", input="x", expect="Four")
    verdict = await grade(
        GraderSpec(kind="exact", config={"case_sensitive": False}), case, Response(text=" four ")
    )
    assert verdict.passed


async def test_exact_requires_string_expect():
    case = Case(id="c", input="x", expect=["not", "a", "string"])
    verdict = await grade(GraderSpec(kind="exact"), case, Response(text="x"))
    assert not verdict.passed
    assert verdict.error


async def test_contains_any_all_none():
    case = Case(id="c", input="x", expect=["red", "blue"])
    assert (await grade(GraderSpec(kind="contains", config={"mode": "any"}), case, Response(text="I like blue"))).passed
    assert not (await grade(GraderSpec(kind="contains", config={"mode": "all"}), case, Response(text="I like blue"))).passed
    assert (await grade(GraderSpec(kind="contains", config={"mode": "all"}), case, Response(text="red and blue"))).passed
    assert (await grade(GraderSpec(kind="contains", config={"mode": "none"}), case, Response(text="I like green"))).passed


async def test_contains_values_override_expect():
    case = Case(id="c", input="x", expect=None)
    verdict = await grade(
        GraderSpec(kind="contains", config={"values": ["fox"]}), case, Response(text="a quick fox")
    )
    assert verdict.passed


async def test_contains_invalid_mode_raises():
    with pytest.raises(ValueError):
        build_grader(GraderSpec(kind="contains", config={"mode": "sometimes"}))


async def test_regex_search_vs_fullmatch():
    case = Case(id="c", input="x")
    assert (await grade(GraderSpec(kind="regex", config={"pattern": r"\d+"}), case, Response(text="code: 42"))).passed
    assert not (
        await grade(GraderSpec(kind="regex", config={"pattern": r"\d+", "fullmatch": True}), case, Response(text="code: 42"))
    ).passed
    assert (
        await grade(GraderSpec(kind="regex", config={"pattern": r"\d+", "fullmatch": True}), case, Response(text="42"))
    ).passed


async def test_regex_flags():
    case = Case(id="c", input="x")
    verdict = await grade(
        GraderSpec(kind="regex", config={"pattern": "^yes$", "flags": ["i"], "fullmatch": True}),
        case,
        Response(text="YES"),
    )
    assert verdict.passed


async def test_regex_requires_pattern():
    with pytest.raises(ValueError):
        build_grader(GraderSpec(kind="regex", config={}))


async def test_unknown_grader_kind_raises():
    with pytest.raises(UnknownGraderError):
        build_grader(GraderSpec(kind="nonexistent"))
