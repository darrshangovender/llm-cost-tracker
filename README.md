<div align="center">

# llm-cost-tracker — token, cost, and latency observability for LLM calls

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![SQLite](https://img.shields.io/badge/SQLite-3-003B57?logo=sqlite&logoColor=white)](https://sqlite.org)
[![Anthropic](https://img.shields.io/badge/Anthropic-Claude-CC785C)](https://anthropic.com)
[![OpenAI](https://img.shields.io/badge/OpenAI-API-412991?logo=openai&logoColor=white)](https://platform.openai.com)
[![Status](https://img.shields.io/badge/Status-Working%20code-blue)](#)

</div>

---

> A thin middleware that wraps the OpenAI and Anthropic Python clients to track **prompt tokens, completion tokens, model, latency, and cost** for every LLM call. Logs to SQLite (or any DB-API connection). Ships with a CLI for stats.

**Why this exists.** Every team building on LLMs hits the same wall: "what is my cost per user this month?" Provider dashboards aggregate at the API-key level, not at the feature or customer level. This library moves the bookkeeping to your side, in your database, where it can be sliced.

---

## What it does

1. **Wraps** your existing OpenAI or Anthropic client with a transparent proxy.
2. **Measures** prompt tokens, completion tokens, wall-clock latency for every request.
3. **Prices** the call using a built-in price table (updated quarterly; overrideable).
4. **Logs** to SQLite by default, or any DB-API connection (Postgres, MySQL).
5. **Tags** each call with arbitrary metadata: user_id, feature, request_id, etc.
6. **Reports** via CLI: cost by model, by feature, by user, top spenders, daily spend.

```python
from llm_cost_tracker import track
from anthropic import Anthropic

client = track(Anthropic(), tags={"feature": "rag-chatbot", "user_id": "u_123"})
resp = client.messages.create(model="claude-sonnet-4-5", max_tokens=512, messages=[...])
# Behind the scenes: tokens + cost + latency written to llm_calls.db
```

```bash
$ llm-cost stats --since "7d ago"
Model                       calls    tokens  cost USD   p50 latency
─────────────────────────────────────────────────────────────────────
claude-sonnet-4-5           1,243   2.1M     $4.21      1.8s
gpt-4o-mini                 3,891   8.7M     $2.61      0.9s
text-embedding-3-small      12,310  4.0M     $0.08      0.2s
                                              ──────
                                              $6.90
```

## Why a wrapper, not a metering proxy

You could put a proxy in front of every LLM call (LiteLLM-style), but proxies introduce latency, a new failure surface, and a deployment dependency. A library that wraps the client object stays inside your existing process, adds <1ms overhead, and lets you tag calls with first-class application context (user_id, feature, request_id) that a proxy would have to receive via headers.

## Repo structure

```
.
├── llm_cost_tracker/
│   ├── __init__.py
│   ├── pricing.py        # provider price table, USD per 1M tokens
│   ├── store.py          # SQLite store, easy to swap for Postgres
│   ├── wrapper.py        # transparent client wrapper
│   └── cli.py            # `llm-cost stats` / `llm-cost top --feature`
├── tests/
│   └── test_wrapper.py
└── pyproject.toml
```

## Price table — `pricing.py`

Per-1M-token USD pricing for the models I use day-to-day. Easy to override:

```python
from llm_cost_tracker.pricing import set_price
set_price("my-fine-tune-v1", input=0.50, output=1.50)  # custom model
```

Built-in coverage includes Claude (Sonnet 4.x, Haiku 4.x), GPT-4o family, text-embedding-3-small/large.

## CLI

```bash
llm-cost stats --since 24h
llm-cost top --by feature --since 30d
llm-cost top --by user_id --limit 10
llm-cost export --format csv > spend-may.csv
```

## Why SQLite by default

You should be able to drop this into a hobby project at zero cost and zero new infra. The store is one file. When you outgrow it, swap to Postgres with one line — the store interface is intentionally tiny.

## Status

- [x] Wrapper for Anthropic Messages API
- [x] Wrapper for OpenAI Chat Completions
- [x] SQLite store
- [x] Pricing table for core models
- [x] CLI: stats, top, export
- [ ] OpenAI Responses API support
- [ ] Streaming token accounting
- [ ] Postgres store adapter (write the same interface)

## Author

Darrshan Govender · Founder, [Agulhas Code](https://agulhascode.co.za)