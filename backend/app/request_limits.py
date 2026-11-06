import asyncio
import re

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class ProjectBodyLimit:
    """Bound project/contract bodies before parsing, including chunked requests."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST":
            await self.app(scope, receive, send)
            return
        path = scope["path"].rstrip("/")
        if path == "/api/projects":
            limit, description = 16384, "Project request exceeds 16 KiB"
        elif re.fullmatch(r"/api/projects/[^/]+/contracts", path):
            limit, description = 1024 * 1024, "Contract request exceeds 1 MiB"
        else:
            await self.app(scope, receive, send)
            return
        body = bytearray()
        try:
            async with asyncio.timeout(10):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    if len(body) + len(chunk) > limit:
                        await JSONResponse({"detail": description}, 413)(scope, receive, send)
                        return
                    body.extend(chunk)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            await JSONResponse({"detail": "Upload exceeded the 10-second read limit"}, 408)(
                scope, receive, send
            )
            return

        async def replay():
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay, send)
