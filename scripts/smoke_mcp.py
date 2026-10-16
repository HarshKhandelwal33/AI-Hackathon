"""Start LogLens over stdio and verify its public MCP surface."""

import asyncio
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    executable = Path(__file__).parents[1] / ".venv" / "Scripts" / "loglens-mcp.exe"
    server = StdioServerParameters(command=str(executable))
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            prompts = await session.list_prompts()
            print("tools:", ", ".join(tool.name for tool in tools.tools))
            print("prompts:", ", ".join(prompt.name for prompt in prompts.prompts))


if __name__ == "__main__":
    asyncio.run(main())
