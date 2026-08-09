import logging

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from api.schemas import ToolCallResult

transcript_logger = logging.getLogger("task-agent")


def log_message(message: BaseMessage) -> None:
    text = str(message.text)
    if isinstance(message, HumanMessage):
        transcript_logger.info(text, extra={"role": "human"})
    elif isinstance(message, AIMessage):
        extra = {"role": "ai"}
        if message.tool_calls:
            extra["tool_calls"] = [
                {"name": tc["name"], "args": tc["args"]} for tc in message.tool_calls
            ]
        transcript_logger.info(text, extra=extra)
    elif isinstance(message, ToolMessage):
        transcript_logger.info(text, extra={"role": "tool", "tool_name": message.name})


def log_new_messages(messages: list[BaseMessage], prev_len: int) -> None:
    for message in messages[prev_len:]:
        log_message(message)


def extract_tool_calls(messages: list[BaseMessage]) -> list[ToolCallResult]:
    """Pair each AIMessage tool call with its ToolMessage result, if resolved yet."""
    responses = {
        message.tool_call_id: str(message.text)
        for message in messages
        if isinstance(message, ToolMessage)
    }
    return [
        ToolCallResult(
            id=tc["id"],
            name=tc["name"],
            args=tc["args"],
            response=responses.get(tc["id"]),
        )
        for message in messages
        if isinstance(message, AIMessage)
        for tc in message.tool_calls
    ]
