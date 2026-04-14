"""
Penny — a budget assistant agent powered by smolagents and the Budget Tracker MCP server.

Usage:
    python penny.py
    python penny.py "How much did I spend in March 2026?"

Requirements:
    pip install smolagents litellm mcp

Model config (env vars):
    PENNY_MODEL     — LiteLLM model string (default: anthropic/claude-sonnet-4-6)
    ANTHROPIC_API_KEY / OPENAI_API_KEY / etc. — provider credentials
"""

import os
import sys

from smolagents import CodeAgent, LiteLLMModel, ToolCollection


MCP_SSE_URL = "http://raspberrypi4.tailad9f80.ts.net:8502/mcp"

MODEL_ID = os.environ.get("PENNY_MODEL", "anthropic/claude-sonnet-4-6")

SYSTEM_PROMPT = """You are Penny, a friendly and precise personal finance assistant.
You have access to the user's Budget Tracker — a tool that stores monthly budgets and
spending transactions. Use it to answer questions, add or update data, and produce
clear summaries.

Guidelines:
- Always confirm the month/year when it matters (default to the current month if unclear).
- Present money amounts clearly (e.g. "₹1,200" or "$1,200").
- When listing transactions or budgets, format them as readable tables or bullet points.
- If a task modifies data (add / delete / update), briefly confirm what was changed.
- Be concise — no unnecessary filler text.
- Today's date context: April 2026.
"""


def build_agent(tools: list) -> CodeAgent:
    model = LiteLLMModel(model_id=MODEL_ID)
    return CodeAgent(
        tools=tools,
        model=model,
        name="penny",
        description="Penny — your personal budget assistant",
        additional_authorized_imports=["json", "datetime"],
        max_steps=10,
    )


def run_once(query: str) -> None:
    """Run a single query and print the result."""
    with ToolCollection.from_mcp(
        {"url": MCP_SSE_URL, "transport": "sse"},
        trust_remote_code=True,
    ) as tool_collection:
        agent = build_agent(list(tool_collection.tools))
        result = agent.run(query, additional_args={"system_prompt": SYSTEM_PROMPT})
        print(result)


def run_interactive() -> None:
    """Start an interactive REPL session with Penny."""
    print("Hi, I'm Penny — your budget assistant. Type 'exit' or Ctrl-C to quit.\n")

    with ToolCollection.from_mcp(
        {"url": MCP_SSE_URL, "transport": "sse"},
        trust_remote_code=True,
    ) as tool_collection:
        agent = build_agent(list(tool_collection.tools))

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
                result = agent.run(
                    query, additional_args={"system_prompt": SYSTEM_PROMPT}
                )
                print(f"Penny: {result}\n")
            except Exception as exc:  # noqa: BLE001
                print(f"Penny: Sorry, something went wrong — {exc}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Single query passed as CLI argument
        run_once(" ".join(sys.argv[1:]))
    else:
        run_interactive()
