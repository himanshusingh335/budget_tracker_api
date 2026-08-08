from langchain_core.language_models import BaseChatModel
from langchain.agents.middleware import HumanInTheLoopMiddleware, SummarizationMiddleware

from core.config import settings


def build_summarization_middleware(model: BaseChatModel) -> SummarizationMiddleware:
    return SummarizationMiddleware(
        model=model,
        keep=("messages", settings.summarization_keep_messages),
    )


def build_human_in_the_loop_middleware() -> HumanInTheLoopMiddleware:
    """Require human approval before any budget write tool runs.

    These map to backend-service's MCP tools (operation_ids set in
    backend-service/app/routers/{budget,transactions}.py) - all data-modifying
    actions, so the agent must pause and get an explicit approve/reject decision
    before the tool actually executes. Read-only tools (get_summary, get_budget,
    get_transactions, run_query, classify_description) and local tools
    (get_current_date) are not gated.
    """
    return HumanInTheLoopMiddleware(
        interrupt_on={
            "add_transaction": {
                "allowed_decisions": ["approve", "reject"],
                "description": "This will add a new transaction. Approve?",
            },
            "update_transaction": {
                "allowed_decisions": ["approve", "reject"],
                "description": "This will modify an existing transaction. Approve?",
            },
            "delete_transaction": {
                "allowed_decisions": ["approve", "reject"],
                "description": "This will permanently delete a transaction. Approve?",
            },
            "add_budget": {
                "allowed_decisions": ["approve", "reject"],
                "description": "This will add a new budget allocation. Approve?",
            },
            "delete_budget": {
                "allowed_decisions": ["approve", "reject"],
                "description": "This will permanently delete a budget allocation. Approve?",
            },
        },
        description_prefix="Tool execution requires approval",
    )
