"""
Penny web endpoint — serves Penny AI over HTTP for the mobile web UI.

POST /penny/chat    → run a query; may return approval_needed
POST /penny/confirm → resolve pending approvals and resume
"""

import asyncio
import json
import os
import uuid
from datetime import date

from agents import Agent, Runner, SQLiteSession, function_tool
from agents.mcp import MCPServerStreamableHttp
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

MCP_URL = os.environ.get("BUDGET_MCP_URL", "http://localhost:8502/mcp")
MODEL = os.environ.get("PENNY_MODEL", "gpt-4o")

WRITE_TOOL_NAMES = [
    "add_transaction_transactions_post",
    "update_transaction_transactions__id__patch",
    "delete_transaction_transactions__id__delete",
    "add_budget_budget_post",
    "delete_budget_budget_delete",
]

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


@function_tool
def get_today() -> dict:
    """Return today's date in the formats used by the Budget Tracker API."""
    today = date.today()
    return {
        "date": today.strftime("%Y-%m-%d"),
        "month_year": today.strftime("%m/%y"),
        "month": today.month,
        "year": today.year,
        "day": today.day,
    }


router = APIRouter(prefix="/penny", tags=["Penny"])

_mcp: MCPServerStreamableHttp | None = None
_agent: Agent | None = None
_lock = asyncio.Lock()
_pending: dict[str, tuple] = {}  # state_id -> (state, session, interruptions)


async def _init() -> None:
    global _mcp, _agent
    if _agent:
        return
    async with _lock:
        if _agent:
            return
        _mcp = MCPServerStreamableHttp(
            name="budget-tracker",
            params={"url": MCP_URL},
            cache_tools_list=True,
            require_approval={"always": {"tool_names": WRITE_TOOL_NAMES}},
        )
        await _mcp.__aenter__()
        _agent = Agent(
            name="Penny",
            instructions=INSTRUCTIONS,
            model=MODEL,
            tools=[get_today],
            mcp_servers=[_mcp],
        )


async def shutdown() -> None:
    if _mcp:
        await _mcp.__aexit__(None, None, None)


def _serialise_interruptions(interruptions: list) -> list[dict]:
    result = []
    for item in interruptions:
        try:
            args = json.loads(item.arguments or "{}")
        except Exception:
            args = {}
        result.append({"tool_name": item.tool_name, "args": args})
    return result


class ChatRequest(BaseModel):
    message: str
    session_id: str = "penny-web"


class ConfirmRequest(BaseModel):
    state_id: str
    decisions: list[bool]  # one bool per interruption in order; True = approve


@router.post("/chat")
async def chat(req: ChatRequest):
    await _init()
    session = SQLiteSession(req.session_id)
    result = await Runner.run(_agent, req.message, session=session)

    if result.interruptions:
        state_id = str(uuid.uuid4())
        _pending[state_id] = (result.to_state(), session, result.interruptions)
        return {
            "type": "approval_needed",
            "state_id": state_id,
            "interruptions": _serialise_interruptions(result.interruptions),
        }

    return {"type": "response", "message": result.final_output}


@router.post("/confirm")
async def confirm(req: ConfirmRequest):
    if req.state_id not in _pending:
        raise HTTPException(404, "Pending approval not found — it may have already been resolved")

    state, session, interruptions = _pending.pop(req.state_id)

    for i, item in enumerate(interruptions):
        approved = req.decisions[i] if i < len(req.decisions) else False
        if approved:
            state.approve(item)
        else:
            state.reject(item, rejection_message="Action declined by user.")

    result = await Runner.run(_agent, state, session=session)

    if result.interruptions:
        state_id = str(uuid.uuid4())
        _pending[state_id] = (result.to_state(), session, result.interruptions)
        return {
            "type": "approval_needed",
            "state_id": state_id,
            "interruptions": _serialise_interruptions(result.interruptions),
        }

    return {"type": "response", "message": result.final_output}
