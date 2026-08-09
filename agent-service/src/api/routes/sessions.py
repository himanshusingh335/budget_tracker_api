import asyncio

from fastapi import APIRouter, Depends
from langchain_core.messages import HumanMessage

from agent.checkpointer import list_sessions as fetch_sessions
from api.deps import get_agent
from api.schemas import SessionInfo, SessionListResponse

router = APIRouter(prefix="/chat", tags=["sessions"])

PREVIEW_MAX_LEN = 80


async def _preview(agent, thread_id: str) -> str | None:
    state = await agent.aget_state({"configurable": {"thread_id": thread_id}})
    for message in state.values.get("messages", []):
        if isinstance(message, HumanMessage):
            text = str(message.text)
            return text if len(text) <= PREVIEW_MAX_LEN else text[:PREVIEW_MAX_LEN] + "…"
    return None


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(agent=Depends(get_agent)):
    rows = await fetch_sessions(agent.checkpointer)
    previews = await asyncio.gather(*(_preview(agent, r["thread_id"]) for r in rows))
    sessions = [
        SessionInfo(session_id=r["thread_id"], last_modified=r["last_modified"], preview=preview)
        for r, preview in zip(rows, previews)
    ]
    return SessionListResponse(sessions=sessions)
