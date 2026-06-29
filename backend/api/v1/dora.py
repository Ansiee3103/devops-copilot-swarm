"""
DORA Metrics API — Industry-standard DevOps performance metrics.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.core.rbac import check_permission
from backend.services.dora_metrics_service import DORAMetricsService

router = APIRouter(prefix="/api/v1/dora", tags=["DORA Metrics"])


@router.get("/metrics")
def get_dora_metrics(
    days:         int     = 30,
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(check_permission("read")),
):
    """Get all four DORA metrics: Deployment Frequency, Lead Time,
    Change Failure Rate, and Mean Time to Recovery."""
    service = DORAMetricsService(db)
    return service.get_all_metrics(days)


@router.get("/frequency")
def deployment_frequency(
    days:         int     = 30,
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(check_permission("read")),
):
    """Deployment Frequency — How often you deploy to production."""
    service = DORAMetricsService(db)
    return service.deployment_frequency(days)


@router.get("/lead-time")
def lead_time(
    days:         int     = 30,
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(check_permission("read")),
):
    """Lead Time for Changes — Time from commit to production."""
    service = DORAMetricsService(db)
    return service.lead_time(days)


@router.get("/failure-rate")
def change_failure_rate(
    days:         int     = 30,
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(check_permission("read")),
):
    """Change Failure Rate — % of deployments causing failures."""
    service = DORAMetricsService(db)
    return service.change_failure_rate(days)


@router.get("/mttr")
def mean_time_to_recovery(
    days:         int     = 30,
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(check_permission("read")),
):
    """Mean Time to Recovery — How fast you recover from failures."""
    service = DORAMetricsService(db)
    return service.mean_time_to_recovery(days)


@router.get("/trends")
def dora_trends(
    days:         int     = 30,
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(check_permission("read")),
):
    """Get daily trend data for deployment metrics."""
    service = DORAMetricsService(db)
    return service.get_trends(days)
