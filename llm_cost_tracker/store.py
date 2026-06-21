"""SQLite-backed call store. Designed to be swappable for any DB-API 2 connection.

The schema is intentionally tiny — one wide table, indexed by timestamp + a
couple of common tag fields. Production users with millions of calls per day
should swap in a Postgres or ClickHouse store; the interface is just three
methods: connect(), log_call(), query().
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_calls (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT NOT NULL,
    provider        TEXT NOT NULL,
    model           TEXT NOT NULL,
    input_tokens    INTEGER NOT NULL,
    output_tokens   INTEGER NOT NULL,
    cost_usd        REAL,
    latency_ms      INTEGER NOT NULL,
    tags_json       TEXT NOT NULL DEFAULT '{}',
    error           TEXT
);
CREATE INDEX IF NOT EXISTS idx_llm_calls_ts ON llm_calls(ts);
CREATE INDEX IF NOT EXISTS idx_llm_calls_model ON llm_calls(model);
"""


@dataclass
class Call:
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float | None
    latency_ms: int
    tags: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class Store:
    """Append-only call log. Thread-safe per connection."""

    def __init__(self, path: str | Path = "llm_calls.db"):
        self.path = str(path)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def log_call(self, call: Call) -> None:
        self._conn.execute(
            "INSERT INTO llm_calls (ts, provider, model, input_tokens, output_tokens, cost_usd, latency_ms, tags_json, error) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                call.ts.isoformat(),
                call.provider,
                call.model,
                call.input_tokens,
                call.output_tokens,
                call.cost_usd,
                call.latency_ms,
                json.dumps(call.tags, sort_keys=True),
                call.error,
            ),
        )
        self._conn.commit()

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        cur = self._conn.execute(sql, params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def close(self) -> None:
        self._conn.close()


_default: Store | None = None


def default_store() -> Store:
    """Process-wide default store at ./llm_calls.db. Lazy-instantiated."""
    global _default
    if _default is None:
        _default = Store()
    return _default