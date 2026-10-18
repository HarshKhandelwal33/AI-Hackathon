# LogLens

LogLens investigates BGL and OpenStack logs in SereneDB. An MCP server retrieves evidence,
and an OpenAI or Gemini agent answers questions for engineers, team leads and managers.

## Setup

Requires Python 3.11+ and a running SereneDB instance.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
Copy-Item .env.example .env
```

Set `SERENEDB_DSN` in `.env` with the database host, port, database, user and password.
Set `AI_PROVIDER` to `gemini` or `openai`, then configure the corresponding API key and
model using `GEMINI_API_KEY` / `GEMINI_MODEL` or `OPENAI_API_KEY` / `OPENAI_MODEL`.
Keep `.env` private; it is excluded from Git.

For a new database, apply the schema and import the structured Loghub CSVs:

```powershell
.\.venv\Scripts\python.exe scripts/setup_db.py
.\.venv\Scripts\python.exe scripts/load_loghub.py --dataset bgl --file data/loghub/BGL/BGL_2k.log_structured.csv
.\.venv\Scripts\python.exe scripts/load_loghub.py --dataset openstack --file data/loghub/OpenStack/OpenStack_2k.log_structured.csv
```

Skip setup and import when using an already populated database. Replace sample ownership
mappings with real team assignments where available.

## Run

```powershell
.\.venv\Scripts\python.exe -m loglens.agent engineer "Investigate the qemu-img missing disk failure in OpenStack"
.\.venv\Scripts\python.exe -m loglens.agent team_lead "Which fatal problem recurs most in BGL and who owns it?"
.\.venv\Scripts\python.exe -m loglens.agent manager "What should we prioritize across BGL and OpenStack?"
```

These commands send the question and retrieved evidence to the configured model provider.
On this machine, the existing database container can be started with
`docker start logsense-serenedb`. Other installations should use their own database setup.

To expose the tools to another MCP client, run `python -m loglens.server` using the project
Python environment. Shell wrappers are included for macOS/Linux.

## Evidence and queries

- `investigate_error`: examples, correlated context and ownership-grouped log counts.
- `search_logs`: ranked examples with dataset, time, severity and component filters.
- `get_nearby_events`: context within 30 minutes, preferring request ID, then node, then component.
- `summarize_logs`: matching log counts grouped by severity, component, template or team.
- `get_log_trend`: counts in hourly, daily or weekly buckets.
- `get_corpus_overview`: coverage and counts for both datasets.

Time filters use an inclusive start and exclusive end. Search results are bounded examples;
frequency claims require aggregation. Log counts do not establish incident counts, impact
or root cause. Component-only correlation is weak, and unmapped ownership remains unknown.

Evidence IDs identify tool results. Full SQL and parameters are saved in `.runs/`; the model
receives compact rows and audit references. Citation checks detect unknown IDs and a limited
set of directly cited log counts. They do not verify every factual claim.

The agent targets two model calls, with a third available for essential missing evidence.
`LOGLENS_MAX_ROUNDS` defaults to `2` tool batches. On the final call, tools are disabled.
Connection failures are cached until restart; correct the connection settings before retrying.

## Checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/smoke_mcp.py
```

See [benchmarks](benchmarks/README.md) for the 15-question evaluation. Profiling uses
`scripts/profile_retrieval.py` and requires a live database. Benchmark agent runs incur
provider usage; `scripts/benchmark_answers.py` requires `--allow-paid` and a unique `--label`.
No measured speed or quality improvement has been established yet.

SereneDB SQL reference: https://serenedb.com/docs/
Loghub datasets: https://github.com/logpai/loghub
