from fastapi import APIRouter, Depends

from agent.checkpointer import list_sessions as fetch_sessions
from api.deps import get_agent
from api.schemas import SessionInfo, SessionListResponse

router = APIRouter(prefix="/chat", tags=["sessions"])


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(agent=Depends(get_agent)):
    rows = await fetch_sessions(agent.checkpointer)
    sessions = [SessionInfo(session_id=r["thread_id"], last_modified=r["last_modified"]) for r in rows]
    return SessionListResponse(sessions=sessions)
