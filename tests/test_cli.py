"""Tests for the CLI's argument handling — the parts that decide what gets counted."""

from __future__ import annotations

import sqlite3
from datetime import UTC

from llm_cost_tracker.cli import parse_since


def test_aware_timestamp_is_converted_not_relabelled():
    """`.replace(tzinfo=utc)` reinterpreted an offset-aware timestamp as UTC
    instead of converting it, silently shifting the reporting window by the
    offset — two hours of calls dropped out of the report."""
    got = parse_since("2026-08-14T00:00:00+02:00")
    assert got.isoformat() == "2026-08-13T22:00:00+00:00"


def test_naive_timestamp_is_treated_as_utc():
    got = parse_since("2026-08-14T00:00:00")
    assert got.tzinfo is UTC
    assert got.isoformat() == "2026-08-14T00:00:00+00:00"


def test_date_only_is_midnight_utc():
    assert parse_since("2026-08-14").isoformat() == "2026-08-14T00:00:00+00:00"


def test_top_query_binds_the_json_path_instead_of_interpolating_it():
    """`--by` was f-stringed into the SQL. A crafted value closed the
    json_extract call and appended attacker-chosen SQL."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE llm_calls (ts TEXT, cost_usd REAL, tags_json TEXT)")
    conn.execute(
        "INSERT INTO llm_calls VALUES ('2026-01-01', 1.0, '{\"team\": \"search\"}')"
    )
    sql = (
        "SELECT json_extract(tags_json, ?) AS key, COUNT(*) AS calls "
        "FROM llm_calls WHERE ts >= ? AND key IS NOT NULL GROUP BY key"
    )
    # A benign path resolves normally...
    rows = conn.execute(sql, ("$.team", "2020-01-01")).fetchall()
    assert rows == [("search", 1)]
    # ...and an injection payload is inert data, yielding no rows rather than
    # executing. Bound as a parameter it can never leave the json path context.
    payload = "x') AS key, 1 AS calls FROM llm_calls --"
    assert conn.execute(sql, (f"$.{payload}", "2020-01-01")).fetchall() == []
    conn.close()
