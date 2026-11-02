from __future__ import annotations

import base64
import binascii
import secrets

from starlette.datastructures import Headers
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send


class BasicAuthMiddleware:
    def __init__(self, app: ASGIApp, *, credentials: str, exempt: frozenset[str] = frozenset()) -> None:
        self._app = app
        self._expected = credentials.encode()
        self._exempt = exempt

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in self._exempt or self._authorized(Headers(scope=scope)):
            await self._app(scope, receive, send)
            return
        response = Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="LanWatch", charset="UTF-8"'})
        await response(scope, receive, send)

    def _authorized(self, headers: Headers) -> bool:
        scheme, _, value = headers.get("authorization", "").partition(" ")
        if scheme.lower() != "basic":
            return False
        try:
            supplied = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError):
            return False
        return secrets.compare_digest(supplied, self._expected)
