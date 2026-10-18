"""Read-only live SQL profile; never calls a model. Output contains log evidence."""
import json
from pathlib import Path
from time import perf_counter
from loglens.config import Settings
from loglens.db import SereneDB
from loglens.queries import LogQueries
from loglens.models import Filters

db = SereneDB(Settings.from_env().dsn)
records = []
try:
    q = LogQueries(db)
    for dataset, term in [("bgl", "data TLB error"), ("openstack", "qemu-img")]:
        operations = [("search", lambda: q.search(Filters(dataset), term, 5)),
                      ("aggregation", lambda: q.summarize(Filters(dataset), "team", text=term))]
        for label, operation in operations:
            started = perf_counter()
            evidence = operation()
            records.append({"kind": label, "seconds": perf_counter()-started, "evidence": evidence.to_dict(),
                            "plan": db.fetch_all("EXPLAIN ANALYZE " + evidence.query, evidence.parameters)})
            if label == "search" and evidence.rows:
                started = perf_counter()
                context = q.nearby(dataset, evidence.rows[0]["event_id"], 3, 3)
                records.append({"kind": "context", "seconds": perf_counter()-started, "evidence": context.to_dict(),
                                "plan": db.fetch_all("EXPLAIN ANALYZE " + context.query, context.parameters)})
finally:
    db.close()
    Path(".runs").mkdir(exist_ok=True)
    Path(".runs/sql-profile.json").write_text(json.dumps(records, default=str, indent=2))
