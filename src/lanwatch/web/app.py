from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from starlette.types import Scope

from .. import __version__
from ..config import Settings
from ..runtime import Services, build_services
from .auth import BasicAuthMiddleware
from .routes import router

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


class RevalidatingStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


def create_app(
    settings: Settings | None = None,
    *,
    services: Services | None = None,
    start_monitor: bool = True,
) -> FastAPI:
    services = services or build_services(settings or Settings())

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        task = asyncio.create_task(services.monitor.run(), name="lanwatch-monitor") if start_monitor else None
        try:
            yield
        finally:
            if task:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            services.close()

    app = FastAPI(
        title="LanWatch",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.services = services

    if services.settings.auth:
        app.add_middleware(
            BasicAuthMiddleware,
            credentials=services.settings.auth.get_secret_value(),
            exempt=frozenset({"/api/health"}),
        )

    app.include_router(router)
    app.mount("/static", RevalidatingStaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})

    return app
