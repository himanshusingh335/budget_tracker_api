"""
Penny — a budget assistant agent powered by smolagents and the Budget Tracker MCP server.

Usage:
    python penny.py
    python penny.py "How much did I spend in March 2026?"

Requirements:
    pip install smolagents litellm mcp

Model config (env vars):
    PENNY_MODEL     — OpenAI model name (default: gpt-4o)
    OPENAI_API_KEY  — your OpenAI API key
"""

import os
import sys

from smolagents import CodeAgent, OpenAIServerModel, ToolCollection


#MCP_URL = "http://raspberrypi4.tailad9f80.ts.net:8502/mcp"
MCP_URL = "http://localhost:8502/mcp"

MODEL_ID = os.environ.get("PENNY_MODEL", "gpt-5.4")


def build_agent(tools: list) -> CodeAgent:
    model = OpenAIServerModel(model_id=MODEL_ID)
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
        {"url": MCP_URL, "transport": "streamable-http"},
        trust_remote_code=True,
    ) as tool_collection:
        agent = build_agent(list(tool_collection.tools))
        result = agent.run(query)
        print(result)


def run_interactive() -> None:
    """Start an interactive REPL session with Penny."""
    print("Hi, I'm Penny — your budget assistant. Type 'exit' or Ctrl-C to quit.\n")

    with ToolCollection.from_mcp(
        {"url": MCP_URL, "transport": "streamable-http"},
        trust_remote_code=True,
        structured_output=True
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
                result = agent.run(query)
                print(f"Penny: {result}\n")
            except Exception as exc:  # noqa: BLE001
                print(f"Penny: Sorry, something went wrong — {exc}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Single query passed as CLI argument
        run_once(" ".join(sys.argv[1:]))
    else:
        run_interactive()
