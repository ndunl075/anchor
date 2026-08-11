"""Response cache (§6.2): key stability/uniqueness, get/put, corrupt-file handling."""
from __future__ import annotations

from anchor.core.cache import ResponseCache, cache_key
from anchor.core.models import Message, Response


def test_cache_key_stable_across_param_dict_order():
    messages = [Message(role="user", content="hi")]
    k1 = cache_key("anthropic", "1", "claude-opus-5", {"temperature": 0, "max_tokens": 10}, messages, None, 0)
    k2 = cache_key("anthropic", "1", "claude-opus-5", {"max_tokens": 10, "temperature": 0}, messages, None, 0)
    assert k1 == k2


def test_cache_key_distinguishes_repeats():
    messages = [Message(role="user", content="hi")]
    k0 = cache_key("anthropic", "1", "m", {}, messages, None, 0)
    k1 = cache_key("anthropic", "1", "m", {}, messages, None, 1)
    assert k0 != k1


def test_cache_key_distinguishes_system_prompt():
    messages = [Message(role="user", content="hi")]
    k_a = cache_key("anthropic", "1", "m", {}, messages, "You are terse.", 0)
    k_b = cache_key("anthropic", "1", "m", {}, messages, "You are verbose.", 0)
    assert k_a != k_b


def test_cache_key_distinguishes_provider_version():
    messages = [Message(role="user", content="hi")]
    k1 = cache_key("anthropic", "1", "m", {}, messages, None, 0)
    k2 = cache_key("anthropic", "2", "m", {}, messages, None, 0)
    assert k1 != k2


def test_get_miss_then_put_then_hit(tmp_path):
    cache = ResponseCache(tmp_path)
    assert cache.get("abc123") is None

    cache.put("abc123", Response(text="hi"))
    loaded = cache.get("abc123")
    assert loaded is not None
    assert loaded.text == "hi"


def test_put_overwrites_on_refresh(tmp_path):
    cache = ResponseCache(tmp_path)
    cache.put("k", Response(text="first"))
    cache.put("k", Response(text="second"))
    assert cache.get("k").text == "second"


def test_corrupt_cache_file_is_a_miss_not_a_crash(tmp_path):
    cache = ResponseCache(tmp_path)
    path = cache._path("badkey")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json at all", encoding="utf-8")
    assert cache.get("badkey") is None
