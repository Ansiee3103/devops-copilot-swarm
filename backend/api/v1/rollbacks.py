"""
Rollback & Deployment Management API.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.core.rbac import check_permission
from backend.services.rollback_service import RollbackService

router = APIRouter(prefix="/api/v1/rollback", tags=["Rollback"])


@router.post("/{deployment_id}")
def rollback_deployment(
    deployment_id: int,
    body:          dict    = None,
    db:            Session = Depends(get_db),
    current_user:  dict    = Depends(check_permission("deploy")),
):
    """Roll back a deployment to the previous version."""
    body    = body or {}
    service = RollbackService(db)

    # Check if rollback is possible
    check = service.can_rollback(deployment_id)
    if not check["can_rollback"]:
        raise HTTPException(status_code=400, detail=check["reason"])

    return service.rollback(
        deployment_id = deployment_id,
        reason        = body.get("reason", "Manual rollback via API"),
        user          = current_user.get("sub", "unknown"),
        auto          = False,
    )


@router.get("/{deployment_id}/check")
def check_rollback(
    deployment_id: int,
    db:            Session = Depends(get_db),
    current_user:  dict    = Depends(check_permission("read")),
):
    """Check if a deployment can be rolled back."""
    service = RollbackService(db)
    return service.can_rollback(deployment_id)


@router.get("/history")
def rollback_history(
    service_name: str     = None,
    limit:        int     = 20,
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(check_permission("read")),
):
    """Get rollback history."""
    service = RollbackService(db)
    return service.get_rollback_history(service_name, limit)
