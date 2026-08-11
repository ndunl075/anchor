"""Local, regex-based persistence redaction (Architecture §9)."""
from __future__ import annotations

import re
from typing import Any

from anchor.core.config import RedactRule


def redact_text(value: str, rules: list[RedactRule]) -> str:
    for rule in rules:
        value = re.sub(rule.pattern, rule.replace, value)
    return value


def redact_value(value: Any, rules: list[RedactRule]) -> Any:
    """Recursively redact every string in JSON-compatible data without mutating it."""
    if isinstance(value, str):
        return redact_text(value, rules)
    if isinstance(value, list):
        return [redact_value(item, rules) for item in value]
    if isinstance(value, dict):
        return {key: redact_value(item, rules) for key, item in value.items()}
    return value
