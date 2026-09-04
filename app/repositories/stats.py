from typing import Optional

from psycopg_pool import ConnectionPool


class StatsRepository:
    """Aggregations for the owner dashboard.

    Spam rows stay in the table but are left out of every count here: the owner
    asked for leads, not for a record of what the honeypot caught.
    """

    def __init__(self, pool: ConnectionPool):
        self.pool = pool

    def overview(self, tenant_id: int) -> dict:
        with self.pool.connection() as conn:
            return conn.execute(
                "SELECT "
                "  COUNT(*) FILTER (WHERE NOT is_spam) AS total, "
                "  COUNT(*) FILTER (WHERE NOT is_spam AND created_at >= now() - interval '7 days') AS last_7_days, "
                "  COUNT(*) FILTER (WHERE NOT is_spam AND created_at >= now() - interval '24 hours') AS last_24_hours, "
                "  COUNT(*) FILTER (WHERE is_spam) AS spam_blocked, "
                "  COUNT(*) FILTER (WHERE NOT is_spam AND geo_status = 'ok') AS enriched, "
                "  MAX(created_at) FILTER (WHERE NOT is_spam) AS last_submission_at "
                "FROM submissions WHERE tenant_id = %s",
                (tenant_id,),
            ).fetchone()

    def by_widget(self, tenant_id: int) -> list[dict]:
        # LEFT JOIN so a widget with no submissions yet still shows up as zero
        # instead of quietly vanishing from the dashboard.
        with self.pool.connection() as conn:
            return conn.execute(
                "SELECT w.id AS widget_id, w.title, w.type, w.active, "
                "  COUNT(s.id) FILTER (WHERE NOT s.is_spam) AS total, "
                "  COUNT(s.id) FILTER (WHERE s.is_spam) AS spam, "
                "  MAX(s.created_at) FILTER (WHERE NOT s.is_spam) AS last_submission_at "
                "FROM widgets w LEFT JOIN submissions s ON s.widget_id = w.id "
                "WHERE w.tenant_id = %s "
                "GROUP BY w.id, w.title, w.type, w.active "
                "ORDER BY total DESC, w.title",
                (tenant_id,),
            ).fetchall()

    def by_country(self, tenant_id: int, limit: int = 20) -> list[dict]:
        with self.pool.connection() as conn:
            return conn.execute(
                "SELECT COALESCE(country, 'Unknown') AS country, country_code, COUNT(*) AS total "
                "FROM submissions WHERE tenant_id = %s AND NOT is_spam "
                "GROUP BY country, country_code ORDER BY total DESC, country LIMIT %s",
                (tenant_id, limit),
            ).fetchall()

    def timeseries(self, tenant_id: int, days: int) -> list[dict]:
        # generate_series fills the quiet days with zeros, so a chart drawn from
        # this never invents a straight line between two distant points.
        with self.pool.connection() as conn:
            return conn.execute(
                "WITH days AS ("
                "  SELECT generate_series("
                "    date_trunc('day', now()) - make_interval(days => %s - 1),"
                "    date_trunc('day', now()), interval '1 day') AS day"
                ") "
                "SELECT d.day::date AS day, COUNT(s.id) AS total "
                "FROM days d LEFT JOIN submissions s "
                "  ON date_trunc('day', s.created_at) = d.day "
                "  AND s.tenant_id = %s AND NOT s.is_spam "
                "GROUP BY d.day ORDER BY d.day",
                (days, tenant_id),
            ).fetchall()
