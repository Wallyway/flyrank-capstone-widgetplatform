from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# Only these prefixes get CORS headers. The admin API deliberately gets none, so
# a page on the internet cannot drive it from a browser at all, even with a key.
PUBLIC_PREFIXES = ("/widget.js", "/static/", "/public/")

ALLOW_METHODS = "GET, POST, OPTIONS"
ALLOW_HEADERS = "Content-Type, Idempotency-Key"
MAX_AGE = "600"


def is_public(path: str) -> bool:
    return any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in PUBLIC_PREFIXES)


class PublicCORSMiddleware(BaseHTTPMiddleware):
    """CORS by hand, applied per path instead of to the whole app.

    Allow-Origin is "*" because these endpoints are meant for any website and
    the platform never sends cookies with them. Credentials stay off, which is
    also what makes "*" legal at all.
    """

    async def dispatch(self, request, call_next):
        if not is_public(request.url.path):
            return await call_next(request)

        origin = request.headers.get("origin")

        # A preflight is an OPTIONS that carries Access-Control-Request-Method.
        # It must be answered here and never reach the route.
        if request.method == "OPTIONS" and request.headers.get("access-control-request-method"):
            requested_headers = request.headers.get("access-control-request-headers", ALLOW_HEADERS)
            return Response(
                status_code=204,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": ALLOW_METHODS,
                    "Access-Control-Allow-Headers": requested_headers,
                    "Access-Control-Max-Age": MAX_AGE,
                    "Vary": "Origin",
                },
            )

        response = await call_next(request)
        if origin:
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Vary"] = "Origin"
        return response
