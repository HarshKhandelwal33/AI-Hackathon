# LogLens: Simple Guide

## What this project does

LogLens helps people understand large system logs using an AI agent.

You ask a question in normal English. Gemini chooses the correct MCP tools, the tools query
the real BGL and OpenStack logs stored in SereneDB, and Gemini explains the evidence for the
selected role.

```text
Your question
    -> Gemini AI agent
    -> LogLens MCP tools
    -> SereneDB queries
    -> Real BGL/OpenStack log evidence
    -> Role-specific answer
```

The same agent supports three roles:

- `engineer`: finds the failure and nearby log events.
- `team_lead`: shows recurring problems, counts, trends, and responsible teams.
- `manager`: summarizes what should be prioritized and why.

## Run it

On this Windows machine, start Docker Desktop, then open a VS Code PowerShell terminal:

```powershell
cd D:\Hackathon\AI-Hackathon
docker start logsense-serenedb
.\.venv\Scripts\python.exe -m loglens.agent engineer "Investigate the qemu-img missing disk failure in OpenStack"
.\.venv\Scripts\python.exe -m loglens.agent team_lead "Which fatal problem recurs most in BGL and who owns it?"
.\.venv\Scripts\python.exe -m loglens.agent manager "What should we prioritize across BGL and OpenStack?"
```

These agent commands send the question and selected log evidence to the configured model provider.
For a clean checkout, follow README.md to create the environment, install dependencies,
configure the provided SereneDB connection, and load data. The container name above is
specific to this machine. On macOS/Linux the included agent.sh wrapper is also available.

You can replace the text inside quotes with your own question.

## Gemini configuration

The `.env` file must contain:

```dotenv
AI_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.8-flash
SERENEDB_DSN=host=127.0.0.1 port=7890 dbname=postgres user=postgres password=YOUR_DATABASE_PASSWORD
```

Do not commit or share the `.env` file because it contains your API key.

## What you should see

Lines such as this prove that Gemini is selecting and calling MCP tools:

```text
[agent] calling search_logs(...)
[agent] calling get_nearby_events(...)
```

The final answer is generated from query results returned by SereneDB. The database currently
contains the full imported corpora:

- BGL: 4,747,963 log rows
- OpenStack: 207,820 log rows
- Total: 4,955,783 log rows

These are log-row counts, not automatically separate incident counts.

## Other useful commands

Run a dynamic database query without AI:

```bash
./ask.sh engineer openstack "qemu-img Could not open"
```

Run the fixed five-minute offline demonstration:

```bash
./run.sh
```

Verify the MCP tools and tests:

```bash
python scripts/smoke_mcp.py
python -m unittest discover -s tests -v
```

## Important notes

- `agent.sh` is the real AI agent. Gemini decides which MCP tools to call.
- `ask.sh` runs fresh SereneDB queries but does not use AI.
- `run.sh` is a deterministic demo; its explanation is fixed, while its numbers come from
  live database queries.
- `http://127.0.0.1:7890` will not open as a website. Port `7890` uses the PostgreSQL database
  protocol, not HTTP.
- Gemini free-tier rate limits can make the agent pause and retry. This does not mean
  SereneDB has stopped working.

## Stop and restart

Stop SereneDB when finished:

```bash
docker stop logsense-serenedb
```

Start it again later:

```bash
docker start logsense-serenedb
```
