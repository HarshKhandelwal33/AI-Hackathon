from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol

from .models import Bucket, Dataset, Evidence, Filters, GroupBy

if TYPE_CHECKING:
    from .db import QueryRunner
else:
    class QueryRunner(Protocol):
        def fetch_all(self, query: str, parameters: list[Any]) -> list[dict[str, Any]]: ...

TABLES: dict[Dataset, str] = {"bgl": "bgl_logs", "openstack": "openstack_logs"}
INDEXES: dict[Dataset, str] = {"bgl": "bgl_logs_idx", "openstack": "openstack_logs_idx"}
ALLOWED_GROUPS: dict[GroupBy, str] = {
    "component": "l.component",
    "team": "COALESCE(o.team, 'unmapped')",
    "severity": "COALESCE(l.severity, 'unknown')",
    "event_template": "COALESCE(l.event_template, l.message)",
}


def _validate_window(start: datetime | None, end: datetime | None) -> None:
    if start and end and start >= end:
        raise ValueError("start must be earlier than end")


def _filters(filters: Filters, alias: str = "l") -> tuple[list[str], list[Any]]:
    _validate_window(filters.start, filters.end)
    clauses: list[str] = []
    parameters: list[Any] = []
    for expression, value in (
        (f"{alias}.timestamp >= %s", filters.start),
        (f"{alias}.timestamp < %s", filters.end),
        (f"{alias}.severity = %s", filters.severity),
        (f"{alias}.component = %s", filters.component),
    ):
        if value is not None:
            clauses.append(expression)
            parameters.append(value)
    return clauses, parameters


def _scope(filters: Filters, **extra: Any) -> dict[str, Any]:
    scope = {
        "dataset": filters.dataset,
        "start_inclusive": filters.start.isoformat() if filters.start else None,
        "end_exclusive": filters.end.isoformat() if filters.end else None,
        "severity": filters.severity,
        "component": filters.component,
    }
    scope.update(extra)
    return scope


class LogQueries:
    def __init__(self, database: QueryRunner, max_rows: int = 100):
        self.database = database
        self.max_rows = max_rows

    def search(self, filters: Filters, text: str, limit: int = 20) -> Evidence:
        if not text.strip():
            raise ValueError("text must not be empty")
        limit = min(max(limit, 1), self.max_rows)
        clauses, parameters = _filters(filters)
        clauses.insert(0, "l.message @@ websearch_to_tsquery(%s)")
        parameters.insert(0, text)
        parameters.append(limit + 1)
        query = f"""
SELECT l.event_id, l.timestamp, l.dataset, l.component, l.severity,
       l.node_id, l.request_id, l.event_template, l.message,
       ROUND(BM25(l.tableoid)::NUMERIC, 4) AS relevance
FROM {INDEXES[filters.dataset]} AS l
WHERE {' AND '.join(clauses)}
ORDER BY relevance DESC, l.timestamp
LIMIT %s
""".strip()
        rows = self.database.fetch_all(query, parameters)
        truncated = len(rows) > limit
        return Evidence(
            tool="search_logs",
            scope=_scope(filters, text=text, requested_limit=limit),
            query=query,
            parameters=parameters,
            rows=rows[:limit],
            result_count=min(len(rows), limit),
            truncated=truncated,
            caveats=["Search results are examples; use an aggregation to measure frequency."],
        )

    def nearby(self, dataset: Dataset, event_id: str, before: int = 8, after: int = 8) -> Evidence:
        before = min(max(before, 0), 50)
        after = min(max(after, 0), 50)
        table = TABLES[dataset]
        query = f"""
WITH anchor AS (
  SELECT timestamp, component, node_id, request_id
  FROM {table}
  WHERE event_id = %s
  LIMIT 1
), context AS (
  SELECT l.event_id, l.timestamp, l.dataset, l.component, l.severity,
         l.node_id, l.request_id, l.event_template, l.message,
         ROW_NUMBER() OVER (ORDER BY l.timestamp, l.event_id) AS position,
         SUM(CASE WHEN l.event_id = %s THEN 1 ELSE 0 END)
           OVER (ORDER BY l.timestamp, l.event_id) AS anchor_seen
  FROM {table} l, anchor a
  WHERE (l.node_id = a.node_id OR l.request_id = a.request_id OR l.component = a.component)
    AND l.timestamp BETWEEN a.timestamp - INTERVAL '30 minutes'
                        AND a.timestamp + INTERVAL '30 minutes'
), marked AS (
  SELECT *, MAX(CASE WHEN event_id = %s THEN position END) OVER () AS anchor_position
  FROM context
)
SELECT event_id, timestamp, dataset, component, severity, node_id, request_id,
       event_template, message
FROM marked
WHERE position BETWEEN anchor_position - %s AND anchor_position + %s
ORDER BY timestamp, event_id
""".strip()
        parameters: list[Any] = [event_id, event_id, event_id, before, after]
        rows = self.database.fetch_all(query, parameters)
        return Evidence(
            tool="get_nearby_events",
            scope={"dataset": dataset, "event_id": event_id, "before": before, "after": after},
            query=query,
            parameters=parameters,
            rows=rows,
            result_count=len(rows),
            caveats=["Context is correlated by node, request, or component within a 30-minute window."],
        )

    def summarize(
        self, filters: Filters, group_by: GroupBy, limit: int = 20, text: str | None = None
    ) -> Evidence:
        limit = min(max(limit, 1), self.max_rows)
        clauses, parameters = _filters(filters)
        if text is not None:
            if not text.strip():
                raise ValueError("text must not be empty")
            clauses.insert(0, "l.message @@ websearch_to_tsquery(%s)")
            parameters.insert(0, text)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        group = ALLOWED_GROUPS[group_by]
        source = INDEXES[filters.dataset] if text is not None else TABLES[filters.dataset]
        parameters.append(limit + 1)
        query = f"""
SELECT {group} AS group_value,
       COUNT(*) AS log_count,
       COUNT(DISTINCT l.event_template) AS distinct_templates,
       MIN(l.timestamp) AS first_seen,
       MAX(l.timestamp) AS last_seen
FROM {source} l
LEFT JOIN component_ownership o
  ON o.dataset = l.dataset AND o.component = l.component
{where}
GROUP BY {group}
ORDER BY log_count DESC, group_value
LIMIT %s
""".strip()
        rows = self.database.fetch_all(query, parameters)
        truncated = len(rows) > limit
        return Evidence(
            tool="summarize_logs",
            scope=_scope(filters, group_by=group_by, text=text, requested_limit=limit),
            query=query,
            parameters=parameters,
            rows=rows[:limit],
            result_count=min(len(rows), limit),
            truncated=truncated,
            caveats=["Counts measure matching log rows, not necessarily distinct incidents."],
        )

    def trend(
        self, filters: Filters, bucket: Bucket = "day", text: str | None = None
    ) -> Evidence:
        if bucket not in ("hour", "day", "week"):
            raise ValueError("bucket must be hour, day, or week")
        clauses, parameters = _filters(filters)
        if text is not None:
            if not text.strip():
                raise ValueError("text must not be empty")
            clauses.insert(0, "l.message @@ websearch_to_tsquery(%s)")
            parameters.insert(0, text)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        source = INDEXES[filters.dataset] if text is not None else TABLES[filters.dataset]
        query = f"""
SELECT date_trunc('{bucket}', l.timestamp) AS period_start,
       COUNT(*) AS log_count,
       COUNT(DISTINCT l.event_template) AS distinct_templates,
       COUNT(DISTINCT l.component) AS affected_components
FROM {source} l
{where}
GROUP BY period_start
ORDER BY period_start
LIMIT %s
""".strip()
        parameters.append(self.max_rows + 1)
        rows = self.database.fetch_all(query, parameters)
        truncated = len(rows) > self.max_rows
        return Evidence(
            tool="get_log_trend",
            scope=_scope(filters, bucket=bucket, text=text),
            query=query,
            parameters=parameters,
            rows=rows[:self.max_rows],
            result_count=min(len(rows), self.max_rows),
            truncated=truncated,
            caveats=["Counts measure matching log rows, not necessarily distinct incidents.",
                     "Only nonempty buckets are returned. If truncated, narrow the time range or use a coarser bucket."],
        )

    def corpus_overview(self) -> Evidence:
        query = """
SELECT dataset, COUNT(*) AS log_count, MIN(timestamp) AS first_seen,
       MAX(timestamp) AS last_seen, COUNT(DISTINCT component) AS components,
       COUNT(DISTINCT event_template) AS distinct_templates
FROM (
  SELECT dataset, timestamp, component, event_template FROM bgl_logs
  UNION ALL
  SELECT dataset, timestamp, component, event_template FROM openstack_logs
) corpus
GROUP BY dataset
ORDER BY dataset
""".strip()
        rows = self.database.fetch_all(query, [])
        return Evidence(
            tool="get_corpus_overview",
            scope={"datasets": ["bgl", "openstack"], "filters": None},
            query=query,
            parameters=[],
            rows=rows,
            result_count=len(rows),
            caveats=["This is a full-corpus row count for each dataset."],
        )

