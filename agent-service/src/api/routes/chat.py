import json

from fastapi import APIRouter, Depends
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

            run_stream = await agent.astream_events(
                _inputs(request.message), config=config, version="v3"
            )
            async for message in run_stream.messages:
                async for text_delta in message.text:
                    if text_delta:
                        yield {"data": text_delta}

                output = await message.output
                if output.tool_calls:
                    yield {
                        "event": "tool_call",
                        "data": json.dumps(
                            [
                                {"id": tc["id"], "name": tc["name"], "args": tc["args"]}
                                for tc in output.tool_calls
                            ]
                        ),
                    }

            final_state = await agent.aget_state(config)
            new_messages = final_state.values.get("messages", [])[prev_len:]
            log_new_messages(final_state.values.get("messages", []), prev_len)

            if resolved := [tc for tc in extract_tool_calls(new_messages) if tc.response is not None]:
                yield {
                    "event": "tool_result",
                    "data": json.dumps([{"id": tc.id, "response": tc.response} for tc in resolved]),
                }

            if pending := _pending_actions(final_state.interrupts):
                yield {
                    "event": "interrupt",
                    "data": json.dumps([action.model_dump() for action in pending]),
                }
        finally:
            session_id_var.reset(ctx_token)

    return EventSourceResponse(event_generator())
