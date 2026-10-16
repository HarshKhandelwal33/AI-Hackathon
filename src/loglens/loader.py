from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator, Literal

Dataset = Literal["bgl", "openstack"]
LATENCY = re.compile(r"\btime:\s*([0-9.]+)")
UUID = re.compile(r"\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b", re.I)
HEX = re.compile(r"\b[0-9a-f]{16,}\b", re.I)
NUMBER = re.compile(r"\b\d+(?:\.\d+)?\b")
OPENSTACK = re.compile(
    r"^(?P<file>\S+) (?P<date>\d{4}-\d{2}-\d{2}) (?P<time>\S+) "
    r"(?P<pid>\d+) (?P<level>\S+) (?P<logger>\S+)(?: \[(?P<context>[^]]*)\])?(?: (?P<message>.*))?$"
)


def event_template(message: str) -> str:
    """Make a stable, auditable recurrence key without an external log parser."""
    value = UUID.sub("<UUID>", message)
    value = HEX.sub("<HEX>", value)
    return NUMBER.sub("<NUM>", value)


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
    if path.suffix.lower() != ".csv":
        yield from read_raw_rows(path, dataset)
        return
    parser = parse_bgl if dataset == "bgl" else parse_openstack
    with path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            yield parser(row)


def read_raw_rows(path: Path, dataset: Dataset) -> Iterator[tuple[Any, ...]]:
    with path.open(encoding="utf-8", errors="replace") as source:
        for line_number, raw in enumerate(source, 1):
            raw = raw.rstrip("\r\n")
            # PostgreSQL text values cannot contain NUL; preserve the record with a visible marker.
            raw = raw.replace("\x00", "<NUL>")
            if not raw:
                continue
            if dataset == "bgl":
                parts = raw.split(maxsplit=9)
                if len(parts) == 9:
                    parts.append("")
                if len(parts) != 10:
                    raise ValueError(f"{path}:{line_number}: invalid BGL line")
                label, _, _, node, timestamp, _, _, component, level, message = parts
                yield (
                    f"bgl-{line_number}",
                    datetime.strptime(timestamp, "%Y-%m-%d-%H.%M.%S.%f"),
                    "bgl", component, level, node, None, event_template(message),
                    message, None if label == "-" else label, raw,
                )
                continue

            match = OPENSTACK.match(raw)
            if match is None:
                raise ValueError(f"{path}:{line_number}: invalid OpenStack line")
            fields = match.groupdict()
            context = (fields["context"] or "").split()
            request_id = next((item for item in context if item.startswith("req-")), None)
            tenant_id = context[2] if len(context) > 2 and context[2] != "-" else None
            message = fields["message"] or ""
            latency = LATENCY.search(message)
            component = fields["file"].split(".log", 1)[0]
            anomaly = "anomaly" if "abnormal" in path.name else None
            yield (
                f"openstack-{path.stem}-{line_number}",
                datetime.fromisoformat(f"{fields['date']}T{fields['time']}"),
                "openstack", component, fields["level"], None, request_id,
                event_template(message), message, anomaly,
                float(latency.group(1)) * 1000 if latency else None,
                tenant_id, raw,
            )


def batches(rows: Iterable[tuple[Any, ...]], size: int = 2_000) -> Iterator[list[tuple[Any, ...]]]:
    batch: list[tuple[Any, ...]] = []
    for row in rows:
        batch.append(row)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch

