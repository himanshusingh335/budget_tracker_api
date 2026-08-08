import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

from app.logging_config import configure_logging

configure_logging()

from app.config import APP_TITLE, APP_VERSION
from app.middleware import RequestLoggingMiddleware
from app.routers import budget, classify, query, summary, transactions

app = FastAPI(title=APP_TITLE, version=APP_VERSION)

app.add_middleware(RequestLoggingMiddleware)

app.include_router(summary.router)
app.include_router(budget.router)
app.include_router(transactions.router)
app.include_router(query.router)
app.include_router(classify.router)


@app.get("/", tags=["Health"])
def root():
    """Health check endpoint. Returns API status and current version."""
    return {"status": "ok", "version": APP_VERSION}


mcp = FastApiMCP(
    app,
    include_operations=[
        "get_summary",
        "get_budget",
        "add_budget",
        "delete_budget",
        "get_transactions",
        "add_transaction",
        "update_transaction",
        "delete_transaction",
        "run_query",
        "classify_description",
    ],
)
mcp.mount_http()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8502, reload=True)
