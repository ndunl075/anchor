"""OpenAI export logs are JSONL; field shape is selected with ``anchor import --map``."""
from anchor.importers.jsonl import load

__all__ = ["load"]
