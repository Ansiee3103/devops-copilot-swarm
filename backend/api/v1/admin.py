from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.core.rbac import check_permission
from backend.repositories.user_repo import UserRepository
from backend.core.logger import get_logger

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])
logger = get_logger("admin")

@router.get("/users")
def list_users(
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(check_permission("manage_users"))
):
    repo  = UserRepository(db)
    users = repo.get_all()
    return [
        {
            "id":        u.id,
            "username":  u.username,
            "email":     u.email,
            "role":      u.role,
            "is_active": u.is_active,
            "is_admin":  u.is_admin,
            "last_login": str(u.last_login) if u.last_login else None,
            "created_at": str(u.created_at)
        }
        for u in users
    ]

@router.patch("/users/{user_id}/role")
def update_user_role(
    user_id:      int,
    body:         dict,
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(check_permission("manage_users"))
):
    from backend.models.user import User
    from backend.core.rbac import ROLES
    from datetime import datetime, timezone, timedelta

    IST  = timezone(timedelta(hours=5, minutes=30))
    role = body.get("role")

    if role not in ROLES:
        raise HTTPException(
            status_code = 400,
            detail      = f"Invalid role. Valid: {list(ROLES.keys())}"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    old_role  = user.role
    user.role = role
    user.updated_at = datetime.now(IST)
    db.commit()

    logger.info(
        f"Role updated: {user.username} "
        f"{old_role} → {role} "
        f"by {current_user.get('sub')}"
    )

    return {"message": f"Role updated: {user.username} → {role}"}

@router.patch("/users/{user_id}/deactivate")
def deactivate_user(
    user_id:      int,
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(check_permission("manage_users"))
):
    from backend.models.user import User
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False
    db.commit()
    return {"message": f"User {user.username} deactivated"}

@router.get("/audit-logs")
def get_audit_logs(
    limit:        int     = 50,
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(check_permission("manage_org"))
):
    from backend.models.audit import AuditLog
    logs = db.query(AuditLog)\
             .order_by(AuditLog.created_at.desc())\
             .limit(limit)\
             .all()
    return [
        {
            "id":         l.id,
            "username":   l.username,
            "action":     l.action,
            "resource":   l.resource,
            "status":     l.status,
            "ip_address": l.ip_address,
            "created_at": str(l.created_at)
        }
        for l in logs
    ]

@router.get("/system-stats")
def system_stats(
    current_user: dict = Depends(check_permission("admin"))
):
    import psutil, os

    return {
        "cpu_percent":     psutil.cpu_percent(interval=1),
        "memory_percent":  psutil.virtual_memory().percent,
        "disk_percent":    psutil.disk_usage('/').percent,
        "python_version":  f"{__import__('sys').version}",
        "app_version":     "2.0.0",
        "uptime_seconds":  int(psutil.boot_time())
    }