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
    parser.add_argument("--file", type=Path, action="append", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = (row for path in args.file for row in read_rows(path, args.dataset))
    if args.dry_run:
        materialized = list(rows)
        print(f"validated {len(materialized)} {args.dataset} rows")
        if materialized:
            print(f"first event: {materialized[0][0]} at {materialized[0][1].isoformat()}")
        return

    columns = BGL_COLUMNS if args.dataset == "bgl" else OPENSTACK_COLUMNS
    statement = f"COPY {args.dataset}_logs ({columns}) FROM STDIN"
    database = SereneDB(Settings.from_env().dsn)
    loaded = 0
    with database.connection() as connection, connection.cursor() as cursor:
        with cursor.copy(statement) as copy:
            for batch in batches(rows):
                for row in batch:
                    copy.write_row(row)
                loaded += len(batch)
                if loaded % 100_000 == 0:
                    print(f"processed {loaded} rows")
        connection.commit()
    print(f"loaded {loaded} {args.dataset} rows")


if __name__ == "__main__":
    main()

