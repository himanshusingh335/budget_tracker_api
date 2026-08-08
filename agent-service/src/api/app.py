import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from agent.checkpointer import get_checkpointer
from agent.graph import build_agent
from api.routes import chat, history, logs, sessions
from core.logging import configure_logging

logger = logging.getLogger("task-agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    async with get_checkpointer() as checkpointer:
        app.state.agent = await build_agent(checkpointer)
        logger.info("agent initialized")
        yield


def create_app() -> FastAPI:
    app = FastAPI(title="agent-service", lifespan=lifespan)
    app.include_router(chat.router)
    app.include_router(history.router)
    app.include_router(logs.router)
    app.include_router(sessions.router)
    return app
