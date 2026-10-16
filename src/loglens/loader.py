from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator, Literal

Dataset = Literal["bgl", "openstack"]
LATENCY = re.compile(r"\btime:\s*([0-9.]+)")


def parse_bgl(row: dict[str, str]) -> tuple[Any, ...]:
    return (
        f"bgl-{row['LineId']}",
        datetime.strptime(row["Time"], "%Y-%m-%d-%H.%M.%S.%f"),
        "bgl",
        row["Component"],
        row["Level"],
        row["Node"],
        None,
        row["EventTemplate"],
        row["Content"],
        None if row["Label"] == "-" else row["Label"],
        row["Content"],
    )


def parse_openstack(row: dict[str, str]) -> tuple[Any, ...]:
    request_fields = row["ADDR"].split()
    request_id = request_fields[0] if request_fields and request_fields[0].startswith("req-") else None
    tenant_id = request_fields[2] if len(request_fields) > 2 and request_fields[2] != "-" else None
    service = row["Logrecord"].split(".log", 1)[0]
    latency = LATENCY.search(row["Content"])
    return (
        f"openstack-{row['LineId']}",
        datetime.fromisoformat(f"{row['Date']}T{row['Time']}"),
        "openstack",
        service,
        row["Level"],
        None,
        request_id,
        row["EventTemplate"],
        row["Content"],
        None,
        float(latency.group(1)) * 1000 if latency else None,
        tenant_id,
        row["Content"],
    )


def read_rows(path: Path, dataset: Dataset) -> Iterator[tuple[Any, ...]]:
    parser = parse_bgl if dataset == "bgl" else parse_openstack
    with path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            yield parser(row)


def batches(rows: Iterable[tuple[Any, ...]], size: int = 2_000) -> Iterator[list[tuple[Any, ...]]]:
    batch: list[tuple[Any, ...]] = []
    for row in rows:
        batch.append(row)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch

