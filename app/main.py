import logging

from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from app.config import APP_TITLE, APP_VERSION
from app.routers import budget, summary, transactions

app = FastAPI(title=APP_TITLE, version=APP_VERSION)

app.include_router(summary.router)
app.include_router(budget.router)
app.include_router(transactions.router)


@app.get("/", tags=["Health"])
def root():
    """Health check endpoint. Returns API status and current version."""
    return {"status": "ok", "version": APP_VERSION}


mcp = FastApiMCP(app)
mcp.mount_http()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8502, reload=True)
