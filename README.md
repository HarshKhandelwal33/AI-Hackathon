# LogLens MCP

LogLens is an evidence-first MCP server for the National AI Hackathon 2026 challenge
**Making Sense of Logs: The Right Insights for the Right People**. It lets an AI agent ask
bounded questions of BGL and OpenStack logs in SereneDB, then returns both the evidence and
the exact SQL behind it.

## What the challenge requires

The prototype must answer a question for each of three audiences using one base corpus:

| Role | Decision | Required evidence |
|---|---|---|
| Engineer | What failed and what should I check next? | Full-text hits, component, events immediately before and after |
| Team lead | Which problems recur and who owns them? | Whole-scope counts, trends, components and team ownership |
| Manager | What deserves attention first? | Measured frequency, affected components, short prioritized actions |

Every numeric claim must come from a query that actually ran. Search examples do not prove
frequency, log rows are not automatically distinct incidents, and hypotheses must be clearly
separated from observed facts. BGL and OpenStack must both be used; an MCP server is the
recommended interface.

## Implemented workflow

The `analyze_logs` prompt teaches the agent to choose among five tools:

- `search_logs`: bounded BM25 full-text search with dataset, time, severity, and component filters.
- `get_nearby_events`: ordered context around a selected event, correlated by node, request, or component.
- `summarize_logs`: full-scope counts by component, owner team, severity, or event template.
- `get_log_trend`: complete hourly, daily, or weekly count series.
- `get_corpus_overview`: verifies coverage and row counts for both required datasets.

Every response includes the SQL template, bound parameters, scope, rows, result count,
truncation status, and caveats. SQL identifiers come from allowlists and user values are bound
parameters.

## Setup

The repository currently contains only the challenge PDF. Obtain the organizer-provided
SereneDB connection details, loader/schema, and ownership mapping before the judged run.
The included normalized schema is a working fallback if those files are unavailable.

1. Install Python 3.11+ and create an environment:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -e .
   ```

2. Copy `.env.example` to `.env`, or set `SERENEDB_DSN` in the shell. SereneDB uses the
   PostgreSQL wire protocol, normally on port `7890`.

3. Apply `sql/001_schema.sql`, then load the organizer's structured CSVs. The official
   2,000-line samples can be validated and loaded like this:

   ```bash
   python scripts/load_loghub.py --dataset bgl --file data/loghub/BGL/BGL_2k.log_structured.csv --dry-run
   python scripts/load_loghub.py --dataset openstack --file data/loghub/OpenStack/OpenStack_2k.log_structured.csv --dry-run
   # Remove --dry-run after configuring SERENEDB_DSN and applying the schema.
   ```

   Apply the real ownership mapping afterward. `sql/002_sample_ownership.sql` only shows
   the expected shape.

4. Start the server:

   ```bash
   loglens-mcp
   ```

5. Configure an MCP client to run the command `loglens-mcp` with `SERENEDB_DSN` in its
   environment. Select the `analyze_logs` prompt and provide `engineer`, `team_lead`, or
   `manager` plus the question.

## Suggested five-minute demo

1. Call `get_corpus_overview` to prove that both datasets are loaded and state their date spans.
2. Engineer: search a real error phrase, select one event, fetch nearby context, and label the
   likely cause as a hypothesis.
3. Team lead: group the same class of errors by team and show its daily or weekly trend.
4. Manager: prioritize the measured patterns using frequency and affected components only.
5. Open one tool response and show the exact SQL, parameters, scope, and truncation flag.

Record the final real queries and results in a worked-investigation document before submission.
Do not hard-code demo numbers in the README.

## Validation

Run the query-layer tests after installing the package:

```bash
python -m unittest discover -s tests -v
```

The tests verify bounded results, parameter binding, time-window validation, and allowlisted
aggregation dimensions without requiring a live database.

## Known limitations

- The organizer-provided SereneDB instance, loader/schema, ownership table, and datasets were
  absent from this workspace, so a live end-to-end query could not yet be recorded.
- Nearby-event correlation is a transparent heuristic (same node, request, or component within
  30 minutes). Tune it after inspecting the supplied schema and real data.
- Counts are log-row counts. Incident grouping needs an explicit, validated rule before the
  system may claim incident counts.
- Index creation is setup-time SQL. Agent-managed index lifecycle and huge-dataset extensions
  are intentionally deferred until the core workflow is proven.

## References

- SereneDB documentation: <https://serenedb.com/docs/>
- Loghub datasets: <https://github.com/logpai/loghub>
- Zhu et al., *Loghub: A Large Collection of System Log Datasets for AI-driven Log Analytics*, ISSRE 2023.
- Oliner & Stearley, *What Supercomputers Say: A Study of Five System Logs*, DSN 2007 (BGL).
