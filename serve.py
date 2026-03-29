"""
Entrypoint for the textual-serve dashboard container.

Subclasses Server to derive public_url dynamically from the incoming
request's Host header, so static assets and WebSocket URLs are always
correct regardless of which IP/hostname the browser uses to connect.
"""
import aiohttp_jinja2
from aiohttp import web
from textual_serve.server import Server
from typing import Any


class DynamicURLServer(Server):
    """Server that sets public_url per-request from the Host header."""

    @aiohttp_jinja2.template("app_index.html")
    async def handle_index(self, request: web.Request) -> dict[str, Any]:
        scheme = "https" if request.secure else "http"
        self.public_url = f"{scheme}://{request.host}"

        router = request.app.router

        def get_url(route: str, **args) -> str:
            path = router[route].url_for(**args)
            return f"{self.public_url}{path}"

        def get_websocket_url(route: str, **args) -> str:
            url = get_url(route, **args)
            prefix = "wss" if request.secure else "ws"
            return prefix + ":" + url.split(":", 1)[1]

        try:
            font_size = int(request.query.get("fontsize", "16"))
        except ValueError:
            font_size = 16

        return {
            "font_size": font_size,
            "app_websocket_url": get_websocket_url("websocket"),
            "config": {
                "static": {
                    "url": get_url("static", filename="/").rstrip("/") + "/",
                },
            },
            "application": {
                "name": self.title or "Budget Tracker",
            },
        }


if __name__ == "__main__":
    DynamicURLServer(
        "python /app/dashboard.py",
        host="0.0.0.0",
        port=8080,
    ).serve()
