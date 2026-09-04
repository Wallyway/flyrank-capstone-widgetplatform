from pathlib import Path
import time

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

# app/core/db.py -> app/core -> app -> repository root
MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


# Compose starts the db and the app at the same time. The healthcheck covers
# most of it, but this retry means `docker compose up` never races.
def build_pool(dsn: str, wait_seconds: float = 30.0) -> ConnectionPool:
    pool = ConnectionPool(dsn, kwargs={"row_factory": dict_row}, open=True)
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            with pool.connection() as conn:
                conn.execute("SELECT 1")
            return pool
        except Exception:
            if time.monotonic() >= deadline:
                raise
            time.sleep(1.0)


def run_migrations(pool: ConnectionPool) -> list[str]:
    """Apply every .sql file in migrations/ that is not in schema_migrations yet."""
    with pool.connection() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version TEXT PRIMARY KEY, "
            "applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        applied = {row["version"] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()}

    newly_applied = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.name in applied:
            continue
        # One transaction per file, so a failing migration leaves nothing half done.
        with pool.connection() as conn:
            conn.execute(path.read_text())
            conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.name,))
        newly_applied.append(path.name)
    return newly_applied
