import logging

from fastapi import FastAPI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from .config import APP_TITLE, APP_VERSION
from .routers import budget, summary, transactions

app = FastAPI(title=APP_TITLE, version=APP_VERSION)

app.include_router(summary.router)
app.include_router(budget.router)
app.include_router(transactions.router)


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "version": APP_VERSION}
