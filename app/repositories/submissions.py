from typing import Optional

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

COLUMNS = (
    "id, widget_id, tenant_id, data, ip, user_agent, referer, country, country_code, city, "
    "geo_provider, geo_status, is_spam, spam_reason, idempotency_key, created_at"
)


class SubmissionsRepository:
    def __init__(self, pool: ConnectionPool):
        self.pool = pool

    def create(self, submission: dict) -> Optional[dict]:
        """Insert one row, or return None if this idempotency key already exists.

        ON CONFLICT DO NOTHING makes the replay harmless at the database level
        instead of relying on a check-then-insert, which two requests arriving
        together would both pass.
        """
        with self.pool.connection() as conn:
            return conn.execute(
                "INSERT INTO submissions "
                "(widget_id, tenant_id, data, ip, user_agent, referer, country, country_code, city, "
                " geo_provider, geo_status, is_spam, spam_reason, idempotency_key) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (widget_id, idempotency_key) WHERE idempotency_key IS NOT NULL "
                "DO NOTHING "
                f"RETURNING {COLUMNS}",
                (
                    submission["widget_id"],
                    submission["tenant_id"],
                    Jsonb(submission["data"]),
                    submission.get("ip"),
                    submission.get("user_agent"),
                    submission.get("referer"),
                    submission.get("country"),
                    submission.get("country_code"),
                    submission.get("city"),
                    submission.get("geo_provider"),
                    submission.get("geo_status", "unavailable"),
                    submission.get("is_spam", False),
                    submission.get("spam_reason"),
                    submission.get("idempotency_key"),
                ),
            ).fetchone()

    def find_by_idempotency_key(self, widget_id: str, key: str) -> Optional[dict]:
        with self.pool.connection() as conn:
            return conn.execute(
                f"SELECT {COLUMNS} FROM submissions WHERE widget_id = %s AND idempotency_key = %s",
                (widget_id, key),
            ).fetchone()

    def list_for_tenant(self, tenant_id: int, widget_id: Optional[str], limit: int, offset: int) -> list[dict]:
        clauses = ["tenant_id = %s"]
        values: list = [tenant_id]
        if widget_id:
            clauses.append("widget_id = %s")
            values.append(widget_id)
        values.extend([limit, offset])
        with self.pool.connection() as conn:
            return conn.execute(
                f"SELECT {COLUMNS} FROM submissions WHERE {' AND '.join(clauses)} "
                "ORDER BY created_at DESC LIMIT %s OFFSET %s",
                tuple(values),
            ).fetchall()

    def count_for_tenant(self, tenant_id: int, widget_id: Optional[str]) -> int:
        clauses = ["tenant_id = %s"]
        values: list = [tenant_id]
        if widget_id:
            clauses.append("widget_id = %s")
            values.append(widget_id)
        with self.pool.connection() as conn:
            row = conn.execute(
                f"SELECT COUNT(*) AS total FROM submissions WHERE {' AND '.join(clauses)}",
                tuple(values),
            ).fetchone()
            return row["total"]
