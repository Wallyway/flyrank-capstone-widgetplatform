from typing import Optional

from app.repositories.stats import StatsRepository
from app.repositories.submissions import SubmissionsRepository

MAX_PAGE_SIZE = 100


class DashboardService:
    def __init__(self, submissions: SubmissionsRepository, stats: StatsRepository):
        self.submissions = submissions
        self.stats = stats

    def list_submissions(
        self, tenant_id: int, widget_id: Optional[str], limit: int, offset: int, include_spam: bool = False
    ) -> dict:
        limit = max(1, min(limit, MAX_PAGE_SIZE))
        offset = max(0, offset)
        rows = self.submissions.list_for_tenant(tenant_id, widget_id, limit, offset, include_spam)
        total = self.submissions.count_for_tenant(tenant_id, widget_id, include_spam)
        return {
            "items": [self.public_row(row) for row in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    # The raw IP and user agent stay out of the API. The owner needs to know
    # where a lead came from, not enough to fingerprint the person who sent it.
    def public_row(self, row: dict) -> dict:
        return {
            "id": row["id"],
            "widget_id": row["widget_id"],
            "data": row["data"],
            "country": row["country"],
            "country_code": row["country_code"],
            "city": row["city"],
            "geo_status": row["geo_status"],
            "is_spam": row["is_spam"],
            "created_at": row["created_at"],
        }

    def overview(self, tenant_id: int) -> dict:
        row = self.stats.overview(tenant_id)
        total = row["total"] or 0
        enriched = row["enriched"] or 0
        return {
            **row,
            "enriched_percent": round(enriched * 100 / total) if total else 0,
        }

    def by_widget(self, tenant_id: int) -> list[dict]:
        return self.stats.by_widget(tenant_id)

    def geo(self, tenant_id: int) -> list[dict]:
        return self.stats.by_country(tenant_id)

    def timeseries(self, tenant_id: int, days: int) -> list[dict]:
        return self.stats.timeseries(tenant_id, max(1, min(days, 90)))
