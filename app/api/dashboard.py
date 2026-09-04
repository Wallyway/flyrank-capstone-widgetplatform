from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import require_tenant
from app.services.dashboard import DashboardService

router = APIRouter(prefix="/api", tags=["dashboard"])


def get_dashboard(request: Request) -> DashboardService:
    return request.app.state.dashboard


@router.get("/submissions", summary="This tenant's submissions")
def list_submissions(
    widget_id: Optional[str] = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    include_spam: bool = Query(default=False, description="Show what the honeypot caught"),
    service: DashboardService = Depends(get_dashboard),
    tenant: dict = Depends(require_tenant),
):
    return service.list_submissions(tenant["id"], widget_id, limit, offset, include_spam)


@router.get("/stats/overview", summary="Headline counts")
def overview(
    service: DashboardService = Depends(get_dashboard),
    tenant: dict = Depends(require_tenant),
):
    return service.overview(tenant["id"])


@router.get("/stats/by-widget", summary="Per-widget totals")
def by_widget(
    service: DashboardService = Depends(get_dashboard),
    tenant: dict = Depends(require_tenant),
):
    return service.by_widget(tenant["id"])


@router.get("/stats/geo", summary="Where submissions came from")
def geo(
    service: DashboardService = Depends(get_dashboard),
    tenant: dict = Depends(require_tenant),
):
    return service.geo(tenant["id"])


@router.get("/stats/timeseries", summary="Submissions per day")
def timeseries(
    days: int = Query(default=14, ge=1, le=90),
    service: DashboardService = Depends(get_dashboard),
    tenant: dict = Depends(require_tenant),
):
    return service.timeseries(tenant["id"], days)
