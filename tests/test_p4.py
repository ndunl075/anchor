from __future__ import annotations

from anchor.core.models import Case, Response, ToolCall
from anchor.core.stats import paired_bootstrap_ci
from anchor.graders.json_path import JsonPathGrader
from anchor.graders.json_schema import JsonSchemaGrader
from anchor.graders.tool_call import ToolCallGrader


def test_paired_bootstrap_is_reproducible_and_contains_point_estimate():
    values = [-0.2, 0.1, 0.3, 0.0]
    first = paired_bootstrap_ci(values)
    assert first == paired_bootstrap_ci(values)
    assert first[0] <= sum(values) / len(values) <= first[1]


async def test_structured_graders():
    case = Case(id="c", input="x", expect="yes")
    response = Response(text='{"answer": "yes"}', tool_calls=[ToolCall(id="1", name="lookup", arguments={"q": "x"})])

    schema = await JsonSchemaGrader({"schema": {"required": ["answer"], "properties": {"answer": {"type": "string"}}}}).grade(case, response, None)
    path = await JsonPathGrader({"path": "$.answer", "expect": "yes"}).grade(case, response, None)
    tool = await ToolCallGrader({"name": "lookup", "arguments": {"q": "x"}}).grade(case, response, None)

    assert schema.passed and path.passed and tool.passed
