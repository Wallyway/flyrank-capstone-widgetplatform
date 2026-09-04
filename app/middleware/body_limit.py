from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app import config


class BodyLimitMiddleware(BaseHTTPMiddleware):
    """Refuse an oversized body before anything reads it.

    This only looks at Content-Length, which is cheap and stops the obvious
    case. The route checks the real length again after reading, because a
    client can lie about the header or omit it entirely.
    """

    async def dispatch(self, request, call_next):
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > config.MAX_BODY_BYTES:
            return JSONResponse(
                status_code=413,
                content={"error": f"Payload too large: limit is {config.MAX_BODY_BYTES} bytes"},
            )
        return await call_next(request)
