"""Run the submission evidence queries and save their exact results as JSON."""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from loglens.config import Settings
from loglens.db import SereneDB
from loglens.models import Filters
from loglens.queries import LogQueries


def encode(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def main() -> None:
    queries = LogQueries(SereneDB(Settings.from_env().dsn), max_rows=100)
    search = queries.search(Filters("openstack"), "qemu-img Could not open", 10)
    evidence = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "corpus_overview": queries.corpus_overview().to_dict(),
        "engineer_search": search.to_dict(),
        "engineer_context": queries.nearby(
            "openstack", search.rows[0]["event_id"], before=8, after=8
        ).to_dict(),
        "openstack_pattern_by_team": queries.summarize(
            Filters("openstack"), "team", 20, "qemu-img Could not open"
        ).to_dict(),
        "openstack_pattern_hourly": queries.trend(
            Filters("openstack"), "hour", "qemu-img Could not open"
        ).to_dict(),
        "openstack_severity": queries.summarize(
            Filters("openstack"), "severity", 20
        ).to_dict(),
        "openstack_errors_by_team": queries.summarize(
            Filters("openstack", severity="ERROR"), "team", 20
        ).to_dict(),
        "bgl_fatal_patterns": queries.summarize(
            Filters("bgl", severity="FATAL"), "event_template", 10
        ).to_dict(),
        "bgl_tlb_search": queries.search(
            Filters("bgl", severity="FATAL"), "data TLB error interrupt", 5
        ).to_dict(),
        "bgl_tlb_by_team": queries.summarize(
            Filters("bgl", severity="FATAL"), "team", 20,
            "data TLB error interrupt",
        ).to_dict(),
        "bgl_tlb_weekly": queries.trend(
            Filters("bgl", severity="FATAL"), "week", "data TLB error interrupt"
        ).to_dict(),
    }
    destination = Path(__file__).resolve().parents[1] / "artifacts" / "evidence.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(evidence, default=encode, indent=2), encoding="utf-8")
    print(f"wrote {destination}")


if __name__ == "__main__":
    main()
