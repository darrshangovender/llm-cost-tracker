"""CLI: `llm-cost stats` / `llm-cost top` / `llm-cost export`."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timedelta, timezone

from rich.console import Console
from rich.table import Table

from .store import default_store


def parse_since(s: str) -> datetime:
    """Parse '24h', '7d', '30d', or an ISO timestamp into a UTC datetime."""
    m = re.fullmatch(r"(\d+)([hdw])(?:\s*ago)?", s.strip())
    if m:
        n, unit = int(m.group(1)), m.group(2)
        delta = {"h": timedelta(hours=n), "d": timedelta(days=n), "w": timedelta(weeks=n)}[unit]
        return datetime.now(timezone.utc) - delta
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc) if "T" in s else datetime.fromisoformat(s + "T00:00:00+00:00")


def cmd_stats(args) -> int:
    store = default_store()
    since = parse_since(args.since).isoformat()
    rows = store.query(
        "SELECT model, COUNT(*) AS calls, "
        "SUM(input_tokens + output_tokens) AS tokens, "
        "ROUND(SUM(cost_usd), 4) AS cost_usd, "
        "ROUND(AVG(latency_ms), 0) AS avg_latency_ms "
        "FROM llm_calls WHERE ts >= ? GROUP BY model ORDER BY cost_usd DESC",
        (since,),
    )
    console = Console()
    table = Table(title=f"LLM spend since {args.since}", show_lines=False)
    table.add_column("Model", style="bold cyan")
    table.add_column("Calls", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Cost USD", justify="right", style="green")
    table.add_column("Avg latency (ms)", justify="right")
    total_cost = 0.0
    for r in rows:
        cost = r.get("cost_usd") or 0
        total_cost += cost
        table.add_row(r["model"], f"{r['calls']:,}", f"{(r['tokens'] or 0):,}", f"${cost:.4f}", f"{r.get('avg_latency_ms', 0) or 0:,.0f}")
    console.print(table)
    console.print(f"\n[bold]Total: ${total_cost:.4f}[/bold]")
    return 0


def cmd_top(args) -> int:
    store = default_store()
    since = parse_since(args.since).isoformat()
    # Tag values live in the JSON blob — pull them out with SQLite's json_extract.
    rows = store.query(
        f"SELECT json_extract(tags_json, '$.{args.by}') AS key, "
        "COUNT(*) AS calls, "
        "ROUND(SUM(cost_usd), 4) AS cost_usd "
        "FROM llm_calls WHERE ts >= ? AND key IS NOT NULL "
        "GROUP BY key ORDER BY cost_usd DESC LIMIT ?",
        (since, args.limit),
    )
    console = Console()
    table = Table(title=f"Top {args.limit} by {args.by} since {args.since}")
    table.add_column(args.by, style="bold cyan")
    table.add_column("Calls", justify="right")
    table.add_column("Cost USD", justify="right", style="green")
    for r in rows:
        table.add_row(str(r["key"]), f"{r['calls']:,}", f"${r.get('cost_usd', 0) or 0:.4f}")
    console.print(table)
    return 0


def cmd_export(args) -> int:
    store = default_store()
    since = parse_since(args.since).isoformat() if args.since else "1970-01-01T00:00:00+00:00"
    rows = store.query("SELECT * FROM llm_calls WHERE ts >= ? ORDER BY ts", (since,))
    if args.format == "csv":
        w = csv.DictWriter(sys.stdout, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            w.writeheader()
            w.writerows(rows)
    else:
        json.dump(rows, sys.stdout, indent=2)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="llm-cost")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("stats", help="Aggregate spend by model")
    s.add_argument("--since", default="24h")
    s.set_defaults(func=cmd_stats)

    t = sub.add_parser("top", help="Top spenders by tag")
    t.add_argument("--by", required=True, help="Tag key to group by, e.g. feature, user_id")
    t.add_argument("--since", default="7d")
    t.add_argument("--limit", type=int, default=20)
    t.set_defaults(func=cmd_top)

    e = sub.add_parser("export", help="Dump raw call log")
    e.add_argument("--format", choices=["csv", "json"], default="csv")
    e.add_argument("--since", default=None)
    e.set_defaults(func=cmd_export)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())