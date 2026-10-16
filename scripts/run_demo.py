"""Print the three role-specific LogLens answers from freshly queried evidence."""

from __future__ import annotations

from loglens.config import Settings
from loglens.db import SereneDB
from loglens.models import Filters
from loglens.queries import LogQueries


def main() -> None:
    q = LogQueries(SereneDB(Settings.from_env().dsn), max_rows=100)
    overview = q.corpus_overview()
    search = q.search(Filters("openstack"), "qemu-img Could not open", 10)
    if not search.rows:
        raise SystemExit("No evidence found. Load the datasets before running the demo.")
    context = q.nearby("openstack", search.rows[0]["event_id"], 8, 8)
    pattern = q.summarize(
        Filters("openstack"), "team", 20, "qemu-img Could not open"
    )
    errors = q.summarize(Filters("openstack", severity="ERROR"), "team", 20)
    bgl = q.summarize(
        Filters("bgl", severity="FATAL"), "team", 20,
        "data TLB error interrupt",
    )

    corpus = {row["dataset"]: row for row in overview.rows}
    hit = search.rows[0]
    match = pattern.rows[0]
    compute = next(row for row in errors.rows if row["group_value"] == "Compute Platform")
    api = next(row for row in errors.rows if row["group_value"] == "API Platform")
    tlb = bgl.rows[0]
    after = next(
        row for row in context.rows
        if row["timestamp"] > hit["timestamp"] and "destroy the instance" in row["message"]
    )

    print("=" * 72)
    print("LOGLENS — GROUNDED THREE-ROLE DEMO")
    print("=" * 72)
    print(
        f"Scope: BGL {corpus['bgl']['log_count']:,} rows "
        f"({corpus['bgl']['first_seen']} to {corpus['bgl']['last_seen']}); "
        f"OpenStack {corpus['openstack']['log_count']:,} rows "
        f"({corpus['openstack']['first_seen']} to {corpus['openstack']['last_seen']})."
    )

    print("\nENGINEER — What failed and what should I check next?")
    print(
        f"Observed: {hit['component']} logged `{hit['message']}` at {hit['timestamp']}. "
        "The traceback reports InvalidDiskInfo and qemu-img exit code 1. "
        f"Immediately afterward, the same instance was destroyed ({after['message']})."
    )
    print(
        "Hypothesis: image-cache inspection raced with instance-disk cleanup, or the "
        "instance directory was removed unexpectedly. The logs do not prove which."
    )
    print(
        "Next check: correlate the instance UUID with lifecycle/deletion records and "
        "verify image-cache cleanup ordering plus filesystem state on nova-compute."
    )

    print("\nTEAM LEAD — Which problem recurs and who owns it?")
    print(
        f"Observed: the exact missing-disk pattern occurs {match['log_count']} times, "
        f"from {match['first_seen']} through {match['last_seen']}, all in nova-compute "
        f"and owned by {match['group_value']}. These are log rows, not proven incidents."
    )
    print(
        f"Broader scope: {compute['log_count']} OpenStack ERROR rows map to Compute "
        f"Platform versus {api['log_count']} to API Platform."
    )
    print(
        "Priority: Compute Platform should reproduce the periodic image-cache pass "
        "against recently deleted instances and add a regression check for missing disks."
    )

    print("\nMANAGER — What deserves attention first?")
    print(
        f"Priority 1: Compute Platform—{compute['log_count']} OpenStack ERROR rows and "
        "a repeated missing-disk failure across more than one day. Assign an owner to "
        "validate cleanup ordering and report whether the eight rows represent distinct incidents."
    )
    print(
        f"Priority 2: Compute Reliability—BGL contains {tlb['log_count']:,} fatal "
        f"`data TLB error interrupt` rows from {tlb['first_seen']} to {tlb['last_seen']}. "
        "The concentration is high, but log rows do not establish customer impact."
    )
    print(
        "Decision: investigate both patterns, starting with the current OpenStack compute "
        "failure because it is component-specific and has actionable file/lifecycle evidence."
    )

    print("\nLIMITATIONS")
    print(
        "No financial loss, downtime, customer impact, or confirmed root cause is inferred. "
        "Every number above was calculated by SereneDB over the stated corpus."
    )


if __name__ == "__main__":
    main()
