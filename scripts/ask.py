"""Query LogLens interactively from the terminal without an MCP client."""

from __future__ import annotations

import argparse

from loglens.config import Settings
from loglens.db import SereneDB
from loglens.models import Filters
from loglens.queries import LogQueries


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask a role-specific question about the logs")
    parser.add_argument("role", choices=("engineer", "team_lead", "manager"))
    parser.add_argument("dataset", choices=("bgl", "openstack"))
    parser.add_argument("question", help="Full-text search terms, e.g. 'qemu-img Could not open'")
    parser.add_argument("--severity")
    parser.add_argument("--component")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    queries = LogQueries(SereneDB(Settings.from_env().dsn), max_rows=100)
    filters = Filters(args.dataset, severity=args.severity, component=args.component)
    search = queries.search(filters, args.question, args.limit)

    print("=" * 72)
    print(f"LOGLENS | {args.role.upper()} | {args.dataset.upper()}")
    print(f"Question/search: {args.question}")
    print("=" * 72)
    print(f"Search returned {search.result_count} row(s); truncated={search.truncated}.")
    if not search.rows:
        print("No matching evidence. Try fewer or broader search terms.")
        return

    if args.role == "engineer":
        hit = search.rows[0]
        context = queries.nearby(args.dataset, hit["event_id"], 5, 5)
        print("\nTOP MATCH")
        print(f"{hit['timestamp']} | {hit['component']} | {hit['severity']} | {hit['message']}")
        print("\nNEARBY EVENTS")
        for row in context.rows:
            marker = ">" if row["event_id"] == hit["event_id"] else " "
            print(f"{marker} {row['timestamp']} | {row['severity']} | {row['message']}")
        print("\nNEXT CHECK")
        print("Correlate the event identifier, node/request, and component with the surrounding lifecycle records.")
    else:
        grouped = queries.summarize(filters, "team", 20, args.question)
        trend = queries.trend(filters, "day", args.question)
        print("\nMEASURED COUNTS BY OWNER TEAM")
        for row in grouped.rows:
            print(
                f"{row['group_value']}: {row['log_count']} rows; "
                f"first={row['first_seen']}; last={row['last_seen']}"
            )
        print("\nDAILY TREND")
        for row in trend.rows:
            print(f"{row['period_start']}: {row['log_count']} rows")
        if args.role == "team_lead":
            print("\nACTION")
            print("Assign the highest-count owner to validate whether the rows form distinct incidents and reproduce the pattern.")
        else:
            print("\nPRIORITY")
            print("Prioritize the highest measured count with a mapped owner; request incident validation before claiming impact.")

    print("\nAUDIT")
    print("Counts are matching log rows, not automatically distinct incidents. Results came from live SereneDB queries.")


if __name__ == "__main__":
    main()
