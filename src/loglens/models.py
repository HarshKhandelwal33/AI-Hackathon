from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from datetime import datetime
from typing import Any, Literal

Dataset = Literal["bgl", "openstack"]
GroupBy = Literal["component", "team", "severity", "event_template"]
Bucket = Literal["hour", "day", "week"]


@dataclass(frozen=True)
class Filters:
    dataset: Dataset
    start: datetime | None = None
    end: datetime | None = None
    severity: str | None = None
    component: str | None = None


@dataclass
class Evidence:
    tool: str
    scope: dict[str, Any]
    query: str
    parameters: list[Any]
    rows: list[dict[str, Any]]
    result_count: int
    truncated: bool = False
    caveats: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["parameters"] = [
            item.isoformat() if isinstance(item, datetime) else item
            for item in value["parameters"]
        ]
        canonical = json.dumps(value, default=str, sort_keys=True)
        value["evidence_id"] = "E-" + hashlib.sha256(canonical.encode()).hexdigest()[:12]
        return value

