from __future__ import annotations

from datetime import datetime
import asyncio
from typing import Literal

from mcp.server.fastmcp import FastMCP

from .config import Settings
from .db import SereneDB
from .models import Bucket, Dataset, Filters, GroupBy
from .queries import LogQueries

settings = Settings.from_env()
queries = LogQueries(SereneDB(settings.dsn), settings.max_rows)
mcp = FastMCP("LogLens")


@mcp.tool()
def search_logs(
    dataset: Dataset,
    text: str,
    start: datetime | None = None,
    end: datetime | None = None,
    severity: str | None = None,
    component: str | None = None,
    limit: int = 20,
) -> dict:
    """Find bounded, ranked log evidence. Use for an engineer's error investigation.

    Time filters use an inclusive start and exclusive end. Returned rows are examples and
    cannot establish frequency; call summarize_logs or get_log_trend for measured claims.
    """
    return queries.search(
        Filters(dataset, start, end, severity, component), text, limit
    ).to_dict()


@mcp.tool()
def get_nearby_events(
    dataset: Dataset, event_id: str, before: int = 8, after: int = 8
) -> dict:
    """Return ordered events around one search hit to investigate what preceded and followed it."""
    return queries.nearby(dataset, event_id, before, after).to_dict()


@mcp.tool()
def summarize_logs(
    dataset: Dataset,
    group_by: GroupBy,
    start: datetime | None = None,
    end: datetime | None = None,
    severity: str | None = None,
    component: str | None = None,
    text: str | None = None,
    limit: int = 20,
) -> dict:
    """Calculate whole-scope counts by component, owner team, severity, or event template.

    Use this for team-lead recurrence analysis and manager prioritization. Counts are log
    rows and must not be described as incidents unless a separate incident rule is defined.
    Set text to measure a full-text pattern over the selected scope rather than merely
    counting the limited examples returned by search_logs.
    """
    return queries.summarize(
        Filters(dataset, start, end, severity, component), group_by, limit, text
    ).to_dict()


@mcp.tool()
def get_log_trend(
    dataset: Dataset,
    bucket: Bucket = "day",
    start: datetime | None = None,
    end: datetime | None = None,
    severity: str | None = None,
    component: str | None = None,
    text: str | None = None,
) -> dict:
    """Calculate bounded nonempty time buckets for recurrence and prioritization; check truncation."""
    return queries.trend(
        Filters(dataset, start, end, severity, component), bucket, text
    ).to_dict()


@mcp.tool()
def get_corpus_overview() -> dict:
    """Verify coverage and full-corpus counts for both required datasets."""
    return queries.corpus_overview().to_dict()


@mcp.prompt()
def analyze_logs(role: Literal["engineer", "team_lead", "manager"], question: str) -> str:
    """Create a grounded analysis plan and response for one required audience."""
    role_guidance = {
        "engineer": "Find the failure, component, and nearby events. Suggest a diagnostic check.",
        "team_lead": "Measure recurring patterns and trends, map owners, and recommend what to investigate first.",
        "manager": "Prioritize observed problems using measured frequency and affected components, then propose actions.",
    }
    return f"""You are answering as a log analyst for a {role}.
Question: {question}
Goal: {role_guidance[role]}

Use the tools before answering. For an engineer, use search_logs and get_nearby_events.
For a team lead or manager, use summarize_logs and get_log_trend; use search_logs only
for supporting examples. Check get_corpus_overview when claiming corpus coverage.

Structure the answer as:
1. Observed facts (each tied to a returned query/result)
2. Possible explanation (clearly labelled as a hypothesis)
3. Recommended next action suited to the role
4. Scope, filters, truncation, and unknowns

Never infer financial loss, downtime, customer impact, or root cause unless the returned
data establishes it. A count of log rows is not automatically a count of incidents.
"""


def main() -> None:
    mcp.run(transport="stdio")






@mcp.tool()
def search_related_logs(dataset: Dataset, phrases: list[str], limit: int = 5,
                        start: datetime | None = None, end: datetime | None = None) -> dict:
    """Search up to three explicit related phrases with the same time scope.

    Each result carries its own evidence reference. Overlapping hits must not be added
    together to estimate frequency; use summarize_logs for a measured pattern count.
    """
    if not 1 <= len(phrases) <= 3 or any(not p.strip() for p in phrases):
        raise ValueError("Provide one to three non-empty search phrases")
    return {"results": [queries.search(Filters(dataset, start, end), phrase, limit).to_dict()
                        for phrase in dict.fromkeys(phrases)],
            "caveats": ["Search groups can overlap; results are examples, not frequency."]}

@mcp.tool()
async def investigate_error(dataset: Dataset, text: str, limit: int = 5,
                            start: datetime | None = None, end: datetime | None = None) -> dict:
    """Find error examples and context for the top ranked hit in one request.

    Prefer this for engineer investigations to avoid another model round trip.
    Context uses a separate 30-minute window around the selected event and can extend
    beyond search time filters. Ranking is relevance, not proof of root cause.
    """
    search = await asyncio.to_thread(queries.search, Filters(dataset, start, end), text, min(max(limit, 1), 10))
    result = {"search": search.to_dict()}
    if search.rows:
        nearby = await asyncio.to_thread(queries.nearby, dataset, search.rows[0]["event_id"], 3, 3)
        result["context"] = nearby.to_dict()
    return result


if __name__ == "__main__":
    main()
