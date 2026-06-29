"""
Audit Trail API — Immutable security event log.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.core.rbac import check_permission
from backend.core.audit_trail import audit_trail

router = APIRouter(prefix="/api/v1/audit", tags=["Audit Trail"])


@router.get("/")
def get_audit_log(
    action:       str     = None,
    limit:        int     = 50,
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(check_permission("admin")),
):
    """Get recent audit entries (admin only)."""
    entries = audit_trail.get_recent(db, limit=limit, action=action)
    return [audit_trail.serialize(e) for e in entries]


@router.get("/security")
def get_security_events(
    limit:        int     = 100,
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(check_permission("admin")),
):
    """Get security-related events: logins, role changes, etc."""
    entries = audit_trail.get_security_events(db, limit=limit)
    return [audit_trail.serialize(e) for e in entries]


@router.get("/user/{user_id}")
def get_user_audit(
    user_id:      int,
    limit:        int     = 50,
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(check_permission("admin")),
):
    """Get audit entries for a specific user."""
    entries = audit_trail.get_by_user(db, user_id=user_id, limit=limit)
    return [audit_trail.serialize(e) for e in entries]


@router.get("/resource/{resource}/{resource_id}")
def get_resource_audit(
    resource:     str,
    resource_id:  int,
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(check_permission("read")),
):
    """Get audit trail for a specific resource (e.g., deployment)."""
    entries = audit_trail.get_by_resource(db, resource, resource_id)
    return [audit_trail.serialize(e) for e in entries]
