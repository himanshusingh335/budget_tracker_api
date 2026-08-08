from fastapi import APIRouter, Depends
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from api.deps import get_agent
from api.schemas import ChatHistoryResponse, HistoryMessage, ToolCallInfo

router = APIRouter(prefix="/chat", tags=["history"])


def _serialize(message: BaseMessage) -> HistoryMessage | None:
    if isinstance(message, HumanMessage):
        return HistoryMessage(role="user", content=str(message.text))
    if isinstance(message, AIMessage):
        tool_calls = (
            [ToolCallInfo(id=tc["id"], name=tc["name"], args=tc["args"]) for tc in message.tool_calls]
            if message.tool_calls
            else None
        )
        return HistoryMessage(role="ai", content=str(message.text), tool_calls=tool_calls)
    if isinstance(message, ToolMessage):
        return HistoryMessage(
            role="tool",
            content=str(message.text),
            tool_call_id=message.tool_call_id,
            tool_name=message.name,
        )
    return None


@router.get("/{session_id}/history", response_model=ChatHistoryResponse)
async def get_history(session_id: str, agent=Depends(get_agent)):
    config = {"configurable": {"thread_id": session_id}}
    state = await agent.aget_state(config)
    raw_messages = state.values.get("messages", [])
    messages = [m for m in (_serialize(msg) for msg in raw_messages) if m is not None]
    return ChatHistoryResponse(session_id=session_id, messages=messages)
