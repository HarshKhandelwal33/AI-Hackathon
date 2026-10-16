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
- `summarize_logs`: full-scope counts by component, owner team, severity, or event template; an optional text query measures a searched pattern across the full scope.
- `get_log_trend`: complete hourly, daily, or weekly count series, optionally filtered by the same full-text pattern.
- `get_corpus_overview`: verifies coverage and row counts for both required datasets.

Every response includes the SQL template, bound parameters, scope, rows, result count,
truncation status, and caveats. SQL identifiers come from allowlists and user values are bound
parameters.

The real agent entry point is `agent.sh`. It sends the role and natural-language question to
an OpenAI or Gemini model, dynamically discovers the five tools from the LogLens MCP server, executes
the model-selected MCP calls against SereneDB, and returns the evidence-grounded answer.
`run.sh` remains a deterministic offline demo and must not be presented as the AI agent.

## Setup

Obtain the organizer-provided SereneDB connection details, datasets, and ownership mapping
before the judged run. This repository includes a normalized schema and loader; the sample
ownership mapping is only a fallback and should be replaced or extended with the official one.

### Local SereneDB

For a local macOS demo, start the official image with a persistent volume. The port is bound
only to loopback; `trust` authentication is appropriate only for local development:

```bash
docker run -d --platform linux/amd64 --name serenedb \
  -p 127.0.0.1:7890:7890 \
  -v serenedb-data:/var/lib/serenedb \
  -e SERENEDB_HOST_AUTH_METHOD=trust \
  serenedb/serenedb
```

The platform flag enables Docker's x86 emulation on Apple Silicon because the current
official image does not publish an arm64 manifest. On Linux x86-64 it can be omitted. Use
`docker stop serenedb` and `docker start serenedb` to stop and resume the database.

1. Install Python 3.11+ and create an environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate              # macOS/Linux
   # .venv\Scripts\activate               # Windows
   pip install -e .
   ```

2. Copy `.env.example` to `.env`, or set `SERENEDB_DSN` in the shell. `.env` is loaded
   automatically. SereneDB uses the PostgreSQL wire protocol, normally on port `7890`.
   To run the actual AI agent, also set `OPENAI_API_KEY`; optionally change `OPENAI_MODEL`.
   For Gemini instead, set `AI_PROVIDER=gemini`, `GEMINI_API_KEY`, and `GEMINI_MODEL`.

3. Apply the schema and sample ownership mapping, then load the organizer's structured
   CSVs:

   ```bash
   python scripts/setup_db.py
   ```

   The official
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

   In another shell, verify MCP discovery without issuing a database query:

   ```bash
   source .venv/bin/activate
   python scripts/smoke_mcp.py
   ```

5. Configure an MCP client with the absolute path to `.venv/bin/loglens-mcp` (or
   `.venv\\Scripts\\loglens-mcp.exe` on Windows) and set its working directory to this
   repository so `.env` is found. Select the `analyze_logs` prompt and provide `engineer`,
   `team_lead`, or `manager` plus the question.

## Tool inputs and outputs

All tools return `scope`, executed `query`, bound `parameters`, `rows`, `result_count`,
`truncated`, and `caveats`. Dataset is `bgl` or `openstack`; timestamps are ISO-8601 with
an inclusive start and exclusive end. Search/summaries accept severity and component;
summaries group by `component`, `team`, `severity`, or `event_template`; trends bucket by
`hour`, `day`, or `week`. Limits are clamped to `LOGLENS_MAX_ROWS`.

## Suggested five-minute demo

For an immediate terminal demo using fresh database queries:

```bash
./run.sh
```

For different questions, use the interactive query command:

```bash
./ask.sh engineer openstack "qemu-img Could not open"
./ask.sh team_lead bgl "data TLB error interrupt" --severity FATAL
./ask.sh manager openstack "No valid host"
```

Run the actual AI agent (the model chooses MCP tools):

```bash
./agent.sh engineer "Investigate the qemu-img missing disk failure in OpenStack"
./agent.sh team_lead "Which fatal problem recurs most in BGL and who owns it?"
./agent.sh manager "What should we prioritize across BGL and OpenStack?"
```

The terminal prints every model-selected tool call as `[agent] calling ...`, making the
agent's tool choice visible during the demonstration.

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
python scripts/smoke_mcp.py
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
