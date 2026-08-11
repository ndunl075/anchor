"""Map traffic records to frozen Anchor cases."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from anchor.core.models import Case, Message
from anchor.core.redact import redact_value
from anchor.core.config import RedactRule


def lookup(record: dict[str, Any], path: str) -> Any:
    """Read a simple dotted path, accepting optional leading dots (``.messages``)."""
    current: Any = record
    for segment in path.lstrip(".").split("."):
        if not segment:
            continue
        if not isinstance(current, dict) or segment not in current:
            return None
        current = current[segment]
    return current


def messages(value: Any) -> list[Message] | None:
    if not isinstance(value, list):
        return None
    try:
        return [Message.model_validate(item) for item in value]
    except Exception:
        return None


def case_from_record(
    record: dict[str, Any], index: int, mappings: dict[str, str], rules: list[RedactRule]
) -> Case:
    input_value = lookup(record, mappings.get("input", ".input"))
    if input_value is None:
        # OpenAI-style logs conventionally carry conversation input in messages.
        input_value = lookup(record, ".messages")
    # Redact the raw JSON-compatible input before turning message dictionaries
    # into Pydantic objects; the redactor deliberately doesn't mutate models.
    input_value = redact_value(input_value, rules)
    parsed_messages = messages(input_value)
    if parsed_messages is not None:
        input_value = parsed_messages
    if not isinstance(input_value, (str, list)):
        raise ValueError("input mapping must resolve to a string or a list of {role, content} messages")

    source_id = lookup(record, mappings.get("id", ".id"))
    if source_id is None:
        source_id = "imported-" + hashlib.sha256(
            json.dumps(record, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:12]
    payload: dict[str, Any] = {"id": str(source_id), "input": input_value}
    for field in ("system", "expect", "tags"):
        if field in mappings:
            value = lookup(record, mappings[field])
            if value is not None:
                payload[field] = value
    payload = redact_value(payload, rules)
    return Case.model_validate(payload)
