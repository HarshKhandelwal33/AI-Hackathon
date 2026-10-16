"""Real LLM agent loop: OpenAI model -> LogLens MCP tools -> SereneDB."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from typing import Any

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import OpenAI, RateLimitError


INSTRUCTIONS = """You are LogLens, an evidence-first log analyst.
You must use the available tools before answering. The database, not your memory,
establishes facts and counts. Match the requested role:
- engineer: identify failure/component, retrieve nearby events, label hypotheses, give next check;
- team_lead: measure recurrence over the full stated scope, show trend and owner, prioritize work;
- manager: prioritize measured risks across the base corpus and give concise actions.
For team_lead and manager, use aggregation/trend tools rather than inferring frequency from
search examples. Use get_corpus_overview for corpus-wide claims. State dataset, time scope,
filters, truncation, and unknowns. A log-row count is not automatically an incident count.
Never invent root cause, financial loss, downtime, or customer impact. Cite tool names and
key returned values in the answer. Keep the answer structured and demo-friendly.
Minimize model round trips: request independent tools together in the same turn. For an
engineer, one search and one nearby-events call are normally enough; use aggregation only
when the question asks how often. Do not repeatedly broaden an investigation after the
requested role has enough evidence.
"""


def mcp_tools_for_openai(mcp_tools: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema,
            "strict": False,
        }
        for tool in mcp_tools
    ]


def mcp_tools_for_chat(mcp_tools: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema,
            },
        }
        for tool in mcp_tools
    ]


async def call_mcp(session: ClientSession, available: set[str], name: str, arguments: str):
    if name not in available:
        return {"error": f"Unknown tool: {name}"}
    values = json.loads(arguments or "{}")
    print(f"[agent] calling {name}({json.dumps(values)})", file=sys.stderr)
    called = await session.call_tool(name, values)
    return called.model_dump(mode="json", exclude_none=True)


async def run_gemini_agent(
    session: ClientSession, discovered: list[Any], role: str, question: str
) -> str:
    key = os.environ["GEMINI_API_KEY"]
    client = OpenAI(
        api_key=key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        default_headers={"x-goog-api-client": "loglens-mcp/0.1.0"},
    )
    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    tools = mcp_tools_for_chat(discovered)
    available = {tool.name for tool in discovered}
    messages: list[Any] = [
        {"role": "system", "content": INSTRUCTIONS},
        {"role": "user", "content": f"Role: {role}\nQuestion: {question}"},
    ]
    for round_number in range(12):
        for retry in range(6):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=tools,
                    tool_choice="required" if round_number == 0 else "auto",
                )
                break
            except RateLimitError as error:
                if retry == 5:
                    raise RuntimeError(
                        "Gemini quota remained exhausted after automatic retries. "
                        "Wait one minute or select a model with available quota."
                    ) from error
                match = re.search(r"retryDelay['\"]?\s*:\s*['\"](\d+)s", str(error))
                delay = max(int(match.group(1)) + 1 if match else 10, 3)
                print(
                    f"[agent] Gemini rate limit reached; retrying in {delay}s "
                    f"({retry + 1}/5)",
                    file=sys.stderr,
                )
                await asyncio.sleep(delay)
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))
        if not message.tool_calls:
            return message.content or ""
        for call in message.tool_calls:
            result = await call_mcp(
                session, available, call.function.name, call.function.arguments
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result),
                }
            )
    raise RuntimeError("Agent exceeded 12 tool-call rounds")


async def run_agent(role: str, question: str) -> str:
    load_dotenv()
    provider = os.getenv("AI_PROVIDER", "openai").lower()
    if provider not in {"openai", "gemini"}:
        raise SystemExit("AI_PROVIDER must be 'openai' or 'gemini'")
    if provider == "gemini" and not os.getenv("GEMINI_API_KEY"):
        raise SystemExit("GEMINI_API_KEY is missing. Add it to .env, then rerun.")
    if provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        raise SystemExit(
            "OPENAI_API_KEY is missing. Add it to .env, then rerun. "
            "Or set AI_PROVIDER=gemini and GEMINI_API_KEY."
        )

    model = os.getenv("OPENAI_MODEL", "gpt-5.4")
    server = StdioServerParameters(command=sys.executable, args=["-m", "loglens.server"])
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            discovered = (await session.list_tools()).tools
            if provider == "gemini":
                return await run_gemini_agent(session, discovered, role, question)
            available = {tool.name for tool in discovered}
            tools = mcp_tools_for_openai(discovered)
            client = OpenAI()
            response = client.responses.create(
                model=model,
                instructions=INSTRUCTIONS,
                input=f"Role: {role}\nQuestion: {question}",
                tools=tools,
                tool_choice="required",
            )

            for _ in range(12):
                calls = [item for item in response.output if item.type == "function_call"]
                if not calls:
                    return response.output_text
                outputs = []
                for call in calls:
                    if call.name not in available:
                        result: Any = {"error": f"Unknown tool: {call.name}"}
                    else:
                        result = await call_mcp(
                            session, available, call.name, call.arguments
                        )
                    outputs.append(
                        {
                            "type": "function_call_output",
                            "call_id": call.call_id,
                            "output": json.dumps(result),
                        }
                    )
                response = client.responses.create(
                    model=model,
                    instructions=INSTRUCTIONS,
                    previous_response_id=response.id,
                    input=outputs,
                    tools=tools,
                    tool_choice="auto",
                )
            raise RuntimeError("Agent exceeded 12 tool-call rounds")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask the LogLens AI agent")
    parser.add_argument("role", choices=("engineer", "team_lead", "manager"))
    parser.add_argument("question")
    args = parser.parse_args()
    print(asyncio.run(run_agent(args.role, args.question)))


if __name__ == "__main__":
    main()
