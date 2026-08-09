import json

from fastapi import APIRouter, Depends
from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage
from langgraph.types import Command, Interrupt
from sse_starlette.sse import EventSourceResponse

from agent.transcript import extract_tool_calls, log_new_messages
from api.deps import get_agent
from api.schemas import ChatRequest, ChatResponse, PendingAction, ResumeRequest
from core.logging import session_id_var

router = APIRouter(prefix="/chat", tags=["chat"])


def _config(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}


def _inputs(message: str) -> dict:
    return {"messages": [{"role": "user", "content": message}]}


def _pending_actions(interrupts: tuple[Interrupt, ...]) -> list[PendingAction] | None:
    actions = [
        PendingAction(name=req["name"], args=req["args"], description=req.get("description"))
        for interrupt in interrupts
        for req in interrupt.value.get("action_requests", [])
    ]
    return actions or None


async def _finish(agent, session_id: str, result: dict, prev_len: int) -> ChatResponse:
    state = await agent.aget_state(_config(session_id))
    tool_calls = extract_tool_calls(result["messages"][prev_len:]) or None
    if pending := _pending_actions(state.interrupts):
        return ChatResponse(session_id=session_id, pending_actions=pending, tool_calls=tool_calls)
    reply = str(result["messages"][-1].text)
    return ChatResponse(session_id=session_id, reply=reply, tool_calls=tool_calls)


@router.post("/invoke", response_model=ChatResponse)
async def invoke(request: ChatRequest, agent=Depends(get_agent)):
    token = session_id_var.set(request.session_id)
    try:
        config = _config(request.session_id)
        state = await agent.aget_state(config)
        prev_len = len(state.values.get("messages", []))

        result = await agent.ainvoke(_inputs(request.message), config=config)

        log_new_messages(result["messages"], prev_len)
        return await _finish(agent, request.session_id, result, prev_len)
    finally:
        session_id_var.reset(token)


@router.post("/resume", response_model=ChatResponse)
async def resume(request: ResumeRequest, agent=Depends(get_agent)):
    """Continue a run that paused for a `remove_task` approval (see build_human_in_the_loop_middleware)."""
    token = session_id_var.set(request.session_id)
    try:
        config = _config(request.session_id)
        state = await agent.aget_state(config)
        prev_len = len(state.values.get("messages", []))

        resume_payload = {
            "decisions": [d.model_dump(exclude_none=True) for d in request.decisions]
        }
        result = await agent.ainvoke(Command(resume=resume_payload), config=config)

        log_new_messages(result["messages"], prev_len)
        return await _finish(agent, request.session_id, result, prev_len)
    finally:
        session_id_var.reset(token)


@router.post("/stream")
async def stream(request: ChatRequest, agent=Depends(get_agent)):
    async def event_generator():
        ctx_token = session_id_var.set(request.session_id)
        try:
            config = _config(request.session_id)
            state = await agent.aget_state(config)
            prev_len = len(state.values.get("messages", []))

            async for chunk in agent.astream(
                _inputs(request.message),
                config=config,
                stream_mode=["messages", "updates"],
                version="v2",
            ):
                if chunk["type"] == "messages":
                    token, _metadata = chunk["data"]
                    if isinstance(token, AIMessageChunk) and token.text:
                        yield {"data": token.text}
                elif chunk["type"] == "updates":
                    for key, update in chunk["data"].items():
                        if key == "__interrupt__" or not update:
                            continue
                        for message in update.get("messages", []):
                            if isinstance(message, AIMessage) and message.tool_calls:
                                yield {
                                    "event": "tool_call",
                                    "data": json.dumps(
                                        [
                                            {"id": tc["id"], "name": tc["name"], "args": tc["args"]}
                                            for tc in message.tool_calls
                                        ]
                                    ),
                                }
                            elif isinstance(message, ToolMessage):
                                yield {
                                    "event": "tool_result",
                                    "data": json.dumps(
                                        [{"id": message.tool_call_id, "response": str(message.text)}]
                                    ),
                                }

            final_state = await agent.aget_state(config)
            log_new_messages(final_state.values.get("messages", []), prev_len)

            if pending := _pending_actions(final_state.interrupts):
                yield {
                    "event": "interrupt",
                    "data": json.dumps([action.model_dump() for action in pending]),
                }
        finally:
            session_id_var.reset(ctx_token)

    return EventSourceResponse(event_generator())
