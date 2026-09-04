from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

import config
from db import build_pool, run_migrations
from tenants_repo import TenantsRepository
from widgets_repo import WidgetsRepository


@asynccontextmanager
async def lifespan(app: FastAPI):
    applied = run_migrations(app.state.pool)
    schema = f"applied {', '.join(applied)}" if applied else "schema up to date"
    print(f"Server running | db ok | {schema}")
    yield
    app.state.pool.close()


app = FastAPI(
    title="Widget & Lead-Capture Platform",
    version="0.1",
    description="Embeddable widgets, a hardened public submission endpoint, and an owner dashboard.",
    lifespan=lifespan,
)

app.state.pool = build_pool(config.DATABASE_URL)
app.state.tenants = TenantsRepository(app.state.pool)
app.state.widgets = WidgetsRepository(app.state.pool)


@app.exception_handler(HTTPException)
def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail}, headers=exc.headers)


def describe_validation_error(error: dict) -> str:
    location = [str(part) for part in error["loc"] if part != "body"]
    field = ".".join(location) if location else "body"
    return f"{field}: {error['msg']}"


# Pydantic would answer 422. The brief asks for a 4xx with a JSON error, so I
# turn it into a 400 with the field name in the message.
@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exc: RequestValidationError):
    details = [describe_validation_error(error) for error in exc.errors()]
    return JSONResponse(status_code=400, content={"error": "; ".join(details)})


@app.get("/health", summary="Health check")
def health():
    with app.state.pool.connection() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok", "database": "ok"}
