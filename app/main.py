from fastapi import FastAPI

from .config import APP_TITLE, APP_VERSION
from .routers import budget, summary, transactions

app = FastAPI(title=APP_TITLE, version=APP_VERSION)

app.include_router(summary.router)
app.include_router(budget.router)
app.include_router(transactions.router)


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "version": APP_VERSION}
