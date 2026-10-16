"""Load Loghub structured CSVs into the normalized SereneDB schema."""

from __future__ import annotations

import argparse
from pathlib import Path

from loglens.config import Settings
from loglens.db import SereneDB
from loglens.loader import batches, read_rows

BGL_COLUMNS = """event_id, timestamp, dataset, component, severity, node_id,
request_id, event_template, message, anomaly_label, raw_line"""
OPENSTACK_COLUMNS = """event_id, timestamp, dataset, component, severity, node_id,
request_id, event_template, message, anomaly_label, latency_ms, tenant_id, raw_line"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=("bgl", "openstack"), required=True)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = read_rows(args.file, args.dataset)
    if args.dry_run:
        materialized = list(rows)
        print(f"validated {len(materialized)} {args.dataset} rows")
        if materialized:
            print(f"first event: {materialized[0][0]} at {materialized[0][1].isoformat()}")
        return

    columns = BGL_COLUMNS if args.dataset == "bgl" else OPENSTACK_COLUMNS
    placeholders = ", ".join(["%s"] * (11 if args.dataset == "bgl" else 13))
    statement = f"INSERT INTO {args.dataset}_logs ({columns}) VALUES ({placeholders}) ON CONFLICT (event_id) DO NOTHING"
    database = SereneDB(Settings.from_env().dsn)
    loaded = 0
    with database.connection() as connection, connection.cursor() as cursor:
        for batch in batches(rows):
            cursor.executemany(statement, batch)
            loaded += len(batch)
            print(f"processed {loaded} rows")
        connection.commit()
    print(f"loaded {loaded} {args.dataset} rows")


if __name__ == "__main__":
    main()

