import json
import logging
import os

from langchain_mcp_adapters.client import MultiServerMCPClient

from core.config import settings

logger = logging.getLogger("task-agent")


async def load_mcp_tools() -> list:
    """Load tools from MCP servers configured in `settings.mcp_config_path`.

    The config file maps server name -> connection dict, e.g.:
        {"my-server": {"transport": "stdio", "command": "npx", "args": [...]}}
    See `mcp_servers.example.json` for the full format. Missing file means no MCP tools.
    """
    if not os.path.exists(settings.mcp_config_path):
        return []

    with open(settings.mcp_config_path) as f:
        connections = json.load(f)

    if not connections:
        return []

    client = MultiServerMCPClient(connections)
    tools = await client.get_tools()
    logger.info("loaded %d MCP tool(s) from %s", len(tools), list(connections))
    return tools
