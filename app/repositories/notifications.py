from typing import Optional

from psycopg_pool import ConnectionPool

JOB_COLUMNS = "id, submission_id, status, attempts, next_attempt_at, last_error"


class NotificationsRepository:
    def __init__(self, pool: ConnectionPool):
        self.pool = pool

    def claim_due(self, limit: int) -> list[dict]:
        """Take the jobs that are due and mark them as being worked on.

        FOR UPDATE SKIP LOCKED means a second worker picks different rows
        instead of waiting, so this scales to more than one process without any
        further coordination.
        """
        with self.pool.connection() as conn:
            return conn.execute(
                "UPDATE notification_jobs SET status = 'processing', attempts = attempts + 1, updated_at = now() "
                "WHERE id IN ("
                "  SELECT id FROM notification_jobs "
                "  WHERE status = 'pending' AND next_attempt_at <= now() "
                "  ORDER BY next_attempt_at LIMIT %s FOR UPDATE SKIP LOCKED"
                ") "
                f"RETURNING {JOB_COLUMNS}",
                (limit,),
            ).fetchall()

    def payload_for(self, submission_id: int) -> Optional[dict]:
        with self.pool.connection() as conn:
            return conn.execute(
                "SELECT s.id, s.widget_id, s.tenant_id, s.data, s.country, s.city, s.created_at, "
                "       w.title AS widget_title "
                "FROM submissions s JOIN widgets w ON w.id = s.widget_id "
                "WHERE s.id = %s",
                (submission_id,),
            ).fetchone()

    def mark_delivered(self, job_id: int):
        with self.pool.connection() as conn:
            conn.execute(
                "UPDATE notification_jobs SET status = 'delivered', last_error = NULL, updated_at = now() "
                "WHERE id = %s",
                (job_id,),
            )

    def reschedule(self, job_id: int, delay_seconds: int, error: str):
        with self.pool.connection() as conn:
            conn.execute(
                "UPDATE notification_jobs SET status = 'pending', last_error = %s, updated_at = now(), "
                "next_attempt_at = now() + make_interval(secs => %s) WHERE id = %s",
                (error[:500], delay_seconds, job_id),
            )

    def mark_dead(self, job_id: int, error: str):
        with self.pool.connection() as conn:
            conn.execute(
                "UPDATE notification_jobs SET status = 'dead', last_error = %s, updated_at = now() WHERE id = %s",
                (error[:500], job_id),
            )

    def counts_by_status(self) -> dict:
        with self.pool.connection() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS total FROM notification_jobs GROUP BY status"
            ).fetchall()
        return {row["status"]: row["total"] for row in rows}
