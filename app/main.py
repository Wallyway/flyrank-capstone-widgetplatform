from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import config
from app.api.widgets import router as widgets_router
from app.core.db import build_pool, run_migrations
from app.core.errors import register_error_handlers
from app.repositories.tenants import TenantsRepository
from app.repositories.widgets import WidgetsRepository
from app.services.widgets import WidgetsService


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

# All the wiring happens here, so no layer below has to know how it was built.
app.state.pool = build_pool(config.DATABASE_URL)
app.state.tenants = TenantsRepository(app.state.pool)
app.state.widgets = WidgetsRepository(app.state.pool)
app.state.widgets_service = WidgetsService(app.state.widgets)

register_error_handlers(app)
app.include_router(widgets_router)


@app.get("/health", summary="Health check")
def health():
    with app.state.pool.connection() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok", "database": "ok"}
