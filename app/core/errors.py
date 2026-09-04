from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def describe_validation_error(error: dict) -> str:
    location = [str(part) for part in error["loc"] if part != "body"]
    field = ".".join(location) if location else "body"
    return f"{field}: {error['msg']}"


def register_error_handlers(app: FastAPI):
    # Registered on Starlette's class, not FastAPI's subclass, so that the 404
    # for an unknown route comes back in the same {"error": ...} shape as
    # everything else instead of FastAPI's default {"detail": ...}.
    @app.exception_handler(StarletteHTTPException)
    def http_exception_handler(request: Request, exc: StarletteHTTPException):
        headers = getattr(exc, "headers", None)
        return JSONResponse(status_code=exc.status_code, content={"error": exc.detail}, headers=headers)

    # Pydantic would answer 422. The brief asks for a 4xx with a JSON error, so
    # this turns it into a 400 with the offending field named in the message.
    @app.exception_handler(RequestValidationError)
    def validation_exception_handler(request: Request, exc: RequestValidationError):
        details = [describe_validation_error(error) for error in exc.errors()]
        return JSONResponse(status_code=400, content={"error": "; ".join(details)})
