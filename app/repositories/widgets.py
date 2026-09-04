from typing import Optional

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

COLUMNS = (
    "id, tenant_id, type, title, description, fields, button_text, options, "
    "config_version, active, created_at, updated_at"
)


# Every method except get_public filters by tenant_id, so there is no way to
# read another tenant's widget from here even by mistake.
class WidgetsRepository:
    def __init__(self, pool: ConnectionPool):
        self.pool = pool

    def create(self, widget_id: str, tenant_id: int, widget: dict) -> dict:
        with self.pool.connection() as conn:
            return conn.execute(
                "INSERT INTO widgets (id, tenant_id, type, title, description, fields, button_text, options) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                f"RETURNING {COLUMNS}",
                (
                    widget_id,
                    tenant_id,
                    widget["type"],
                    widget["title"],
                    widget["description"],
                    Jsonb(widget["fields"]),
                    widget["button_text"],
                    Jsonb(widget["options"]),
                ),
            ).fetchone()

    def list_for_tenant(self, tenant_id: int) -> list[dict]:
        with self.pool.connection() as conn:
            return conn.execute(
                f"SELECT {COLUMNS} FROM widgets WHERE tenant_id = %s ORDER BY created_at DESC",
                (tenant_id,),
            ).fetchall()

    def get_for_tenant(self, widget_id: str, tenant_id: int) -> Optional[dict]:
        with self.pool.connection() as conn:
            return conn.execute(
                f"SELECT {COLUMNS} FROM widgets WHERE id = %s AND tenant_id = %s",
                (widget_id, tenant_id),
            ).fetchone()

    # Used by the public config endpoint, which anyone holding the id may read.
    def get_public(self, widget_id: str) -> Optional[dict]:
        with self.pool.connection() as conn:
            return conn.execute(
                f"SELECT {COLUMNS} FROM widgets WHERE id = %s", (widget_id,)
            ).fetchone()

    def update(self, widget_id: str, tenant_id: int, changes: dict) -> Optional[dict]:
        assignments = []
        values = []
        for column, value in changes.items():
            assignments.append(f"{column} = %s")
            values.append(Jsonb(value) if column in ("fields", "options") else value)
        # Bumped on every edit so a cached config can be told apart from a new one.
        assignments.append("config_version = config_version + 1")
        assignments.append("updated_at = now()")
        values.extend([widget_id, tenant_id])
        with self.pool.connection() as conn:
            return conn.execute(
                f"UPDATE widgets SET {', '.join(assignments)} "
                f"WHERE id = %s AND tenant_id = %s RETURNING {COLUMNS}",
                tuple(values),
            ).fetchone()

    def delete(self, widget_id: str, tenant_id: int) -> bool:
        with self.pool.connection() as conn:
            return conn.execute(
                "DELETE FROM widgets WHERE id = %s AND tenant_id = %s",
                (widget_id, tenant_id),
            ).rowcount > 0
