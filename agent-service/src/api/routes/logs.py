from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Query

from api.schemas import SessionLogsResponse
from core.log_reader import read_session_logs

router = APIRouter(prefix="/chat", tags=["logs"])


@router.get("/{session_id}/logs", response_model=SessionLogsResponse)
async def get_session_logs(
    session_id: str,
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] | None = None,
    logger: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = Query(200, le=1000),
    offset: int = Query(0, ge=0),
):
    entries, total = read_session_logs(
        session_id, level, logger, start_time, end_time, limit, offset
    )
    return SessionLogsResponse(
        session_id=session_id, logs=entries, total=total, limit=limit, offset=offset
    )
