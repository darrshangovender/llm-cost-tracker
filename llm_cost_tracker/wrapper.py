"""Transparent wrapper around the OpenAI and Anthropic Python clients.

Design choice: we monkey-patch the .messages.create / .chat.completions.create
method on the supplied client instance rather than subclass the client. Subclassing
breaks when the SDK changes its internal class hierarchy (and they do, often).
Monkey-patching one method is stable.
"""

from __future__ import annotations

import time
from typing import Any

from .pricing import estimate_cost
from .store import Call, Store, default_store


def track(client: Any, *, tags: dict[str, Any] | None = None, store: Store | None = None) -> Any:
    """Wrap an OpenAI or Anthropic client so every call is logged.

    Returns the same client object with the create methods replaced by
    instrumented versions. Subsequent calls work exactly as before.

    `tags` are attached to every call made through this wrapper. To add
    per-call tags, mutate the dict on the wrapper or use a fresh wrapper.
    """
    tags = dict(tags or {})
    store = store or default_store()

    provider = _detect_provider(client)
    if provider == "anthropic":
        _wrap_anthropic(client, tags, store)
    elif provider == "openai":
        _wrap_openai(client, tags, store)
    else:
        raise TypeError(
            f"Unknown LLM client type: {type(client)!r}. "
            "Supported: anthropic.Anthropic, openai.OpenAI."
        )
    client._llm_cost_tags = tags  # expose for mutation
    return client


def _detect_provider(client: Any) -> str:
    cls = type(client).__name__
    if cls.endswith("Anthropic") or "anthropic" in type(client).__module__.lower():
        return "anthropic"
    if cls.endswith("OpenAI") or "openai" in type(client).__module__.lower():
        return "openai"
    return "unknown"


def _wrap_anthropic(client: Any, tags: dict, store: Store) -> None:
    original = client.messages.create

    def create(*args, **kwargs):
        model = kwargs.get("model", "")
        t0 = time.perf_counter()
        try:
            resp = original(*args, **kwargs)
        except Exception as e:
            store.log_call(Call(
                provider="anthropic", model=model,
                input_tokens=0, output_tokens=0, cost_usd=None,
                latency_ms=int((time.perf_counter() - t0) * 1000),
                tags=tags, error=str(e)[:500],
            ))
            raise
        latency_ms = int((time.perf_counter() - t0) * 1000)
        u = getattr(resp, "usage", None)
        in_tokens = getattr(u, "input_tokens", 0) if u else 0
        out_tokens = getattr(u, "output_tokens", 0) if u else 0
        store.log_call(Call(
            provider="anthropic", model=model,
            input_tokens=in_tokens, output_tokens=out_tokens,
            cost_usd=estimate_cost(model, in_tokens, out_tokens),
            latency_ms=latency_ms, tags=tags,
        ))
        return resp

    client.messages.create = create


def _wrap_openai(client: Any, tags: dict, store: Store) -> None:
    original = client.chat.completions.create

    def create(*args, **kwargs):
        model = kwargs.get("model", "")
        t0 = time.perf_counter()
        try:
            resp = original(*args, **kwargs)
        except Exception as e:
            store.log_call(Call(
                provider="openai", model=model,
                input_tokens=0, output_tokens=0, cost_usd=None,
                latency_ms=int((time.perf_counter() - t0) * 1000),
                tags=tags, error=str(e)[:500],
            ))
            raise
        latency_ms = int((time.perf_counter() - t0) * 1000)
        u = getattr(resp, "usage", None)
        in_tokens = getattr(u, "prompt_tokens", 0) if u else 0
        out_tokens = getattr(u, "completion_tokens", 0) if u else 0
        store.log_call(Call(
            provider="openai", model=model,
            input_tokens=in_tokens, output_tokens=out_tokens,
            cost_usd=estimate_cost(model, in_tokens, out_tokens),
            latency_ms=latency_ms, tags=tags,
        ))
        return resp

    client.chat.completions.create = create