import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi_mcp import FastApiMCP

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from app.config import APP_TITLE, APP_VERSION
from app.routers import budget, classify, penny_web, query, summary, transactions


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await penny_web.shutdown()


app = FastAPI(title=APP_TITLE, version=APP_VERSION, lifespan=lifespan)

app.include_router(summary.router)
app.include_router(budget.router)
app.include_router(transactions.router)
app.include_router(query.router)
app.include_router(classify.router)
app.include_router(penny_web.router)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", tags=["Health"])
def root():
    """Health check endpoint. Returns API status and current version."""
    return {"status": "ok", "version": APP_VERSION}


@app.get("/app", include_in_schema=False)
def web_app():
    return FileResponse("static/app.html")


mcp = FastApiMCP(app, exclude_tags=["Penny"])
mcp.mount_http()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8502, reload=True)
