"""
Penny — a budget assistant powered by the OpenAI Agents SDK + Budget Tracker MCP server.

Usage:
    python penny.py
    python penny.py "How much did I spend in March 2026?"

Requirements:
    pip install openai-agents

Config (env vars):
    PENNY_MODEL     — OpenAI model name (default: gpt-4o)
    OPENAI_API_KEY  — your OpenAI API key
"""

import asyncio
import os
import sys
from datetime import date

from agents import Agent, Runner, SQLiteSession, function_tool
from agents.mcp import MCPServerStreamableHttp


MCP_URL = "http://raspberrypi4.tailad9f80.ts.net:8502/mcp"
#MCP_URL = "http://localhost:8502/mcp"

MODEL = os.environ.get("PENNY_MODEL", "gpt-5.4")
SESSION_ID = "penny-default"  # reused across runs so history persists


@function_tool
def get_today() -> dict:
    """Return today's date in the formats used by the Budget Tracker API."""
    today = date.today()
    return {
        "date": today.strftime("%Y-%m-%d"),      # transaction Date field
        "month_year": today.strftime("%m/%y"),   # MonthYear field (MM/YY)
        "month": today.month,
        "year": today.year,
        "day": today.day,
    }


INSTRUCTIONS = (
    "You are Penny, a concise and friendly personal budget assistant. "
    "Use the available tools to answer questions about the user's budgets and transactions. "
    "Formatting rules you must always follow:\n"
    "1. Currency: always prefix amounts with ₹ and no other symbol. Never use 'INR' or 'Rs'.\n"
    "2. Number formatting: use Indian-style comma grouping (e.g. ₹1,23,456.00 not ₹123,456.00).\n"
    "3. Structure: present any comparison, breakdown, or multi-item answer as a plain-text table "
    "using aligned columns. Use a table even for two rows if there are multiple fields.\n"
    "4. Brevity: keep prose to one sentence max; let the table carry the detail."
)


async def run_once(query: str) -> None:
    """Run a single query and print the result."""
    async with MCPServerStreamableHttp(
        name="budget-tracker",
        params={"url": MCP_URL},
        cache_tools_list=True,
    ) as server:
        agent = Agent(
            name="Penny",
            instructions=INSTRUCTIONS,
            model=MODEL,
            tools=[get_today],
            mcp_servers=[server],
        )
        result = await Runner.run(agent, query)
        print(result.final_output)


async def run_interactive() -> None:
    """Start an interactive REPL session with Penny. History is kept via SQLiteSession."""
    print("Hi, I'm Penny — your budget assistant. Type 'exit' or Ctrl-C to quit.\n")

    session = SQLiteSession(SESSION_ID)

    async with MCPServerStreamableHttp(
        name="budget-tracker",
        params={"url": MCP_URL},
        cache_tools_list=True,
    ) as server:
        agent = Agent(
            name="Penny",
            instructions=INSTRUCTIONS,
            model=MODEL,
            tools=[get_today],
            mcp_servers=[server],
        )

        while True:
            try:
                query = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            if not query:
                continue
            if query.lower() in {"exit", "quit", "bye"}:
                print("Penny: Goodbye! Stay on budget.")
                break

            try:
                result = await Runner.run(agent, query, session=session)
                print(f"Penny: {result.final_output}\n")
            except Exception as exc:  # noqa: BLE001
                print(f"Penny: Sorry, something went wrong — {exc}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        asyncio.run(run_once(" ".join(sys.argv[1:])))
    else:
        asyncio.run(run_interactive())
