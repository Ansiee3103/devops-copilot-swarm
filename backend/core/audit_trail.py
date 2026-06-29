"""
Immutable Audit Trail — Tracks all security-sensitive actions.
Entries are append-only and cannot be deleted via the API.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from backend.models.audit import AuditLog
from backend.core.logger import get_logger

logger = get_logger("audit_trail")
IST    = timezone(timedelta(hours=5, minutes=30))


class AuditTrail:
    """Append-only audit logger for security-critical events."""

    # ── Action Constants ─────────────────────────────────
    LOGIN_SUCCESS      = "auth.login.success"
    LOGIN_FAILED       = "auth.login.failed"
    LOGOUT             = "auth.logout"
    TOKEN_REFRESH      = "auth.token.refresh"
    USER_CREATED       = "user.created"
    USER_ROLE_CHANGED  = "user.role_changed"
    DEPLOY_STARTED     = "deploy.started"
    DEPLOY_COMPLETED   = "deploy.completed"
    DEPLOY_BLOCKED     = "deploy.blocked"
    DEPLOY_FAILED      = "deploy.failed"
    DEPLOY_ROLLBACK    = "deploy.rollback"
    DEPLOY_APPROVED    = "deploy.approved"
    DEPLOY_REJECTED    = "deploy.rejected"
    HEAL_STARTED       = "heal.started"
    HEAL_COMPLETED     = "heal.completed"
    CONFIG_CHANGED     = "config.changed"
    HISTORY_CLEARED    = "admin.history_cleared"
    SECRET_ROTATED     = "security.secret_rotated"

    def log(
        self,
        db:          Session,
        action:      str,
        user_id:     Optional[int]  = None,
        username:    Optional[str]  = None,
        resource:    Optional[str]  = None,
        resource_id: Optional[int]  = None,
        details:     Optional[str]  = None,
        ip_address:  Optional[str]  = None,
        user_agent:  Optional[str]  = None,
        status:      str            = "success",
    ) -> AuditLog:
        """
        Record an immutable audit event.

        Parameters
        ----------
        db          : Active SQLAlchemy session.
        action      : One of the AuditTrail.*_CONSTANTS or a custom action.
        user_id     : ID of the acting user (None for system actions).
        username    : Human-readable username for fast lookup.
        resource    : Resource type being acted upon (e.g. 'deployment').
        resource_id : ID of the resource.
        details     : Free-form JSON or text with extra context.
        ip_address  : Client IP address.
        user_agent  : Client user-agent string.
        status      : 'success' or 'failed'.
        """
        entry = AuditLog(
            user_id     = user_id,
            username    = username or "system",
            action      = action,
            resource    = resource,
            resource_id = resource_id,
            details     = details,
            ip_address  = ip_address,
            user_agent  = user_agent,
            status      = status,
        )
        try:
            db.add(entry)
            db.commit()
            db.refresh(entry)
            logger.info(
                f"📋 Audit: {action} by {username or 'system'} "
                f"on {resource or '-'}#{resource_id or '-'} [{status}]"
            )
        except Exception as e:
            db.rollback()
            logger.error(f"Audit log write failed: {e}")
        return entry

    # ── Query Helpers ─────────────────────────────────────

    def get_recent(
        self, db: Session, limit: int = 50, action: str = None
    ) -> list:
        """Get recent audit entries, optionally filtered by action."""
        query = db.query(AuditLog).order_by(AuditLog.created_at.desc())
        if action:
            query = query.filter(AuditLog.action == action)
        return query.limit(limit).all()

    def get_by_user(
        self, db: Session, user_id: int, limit: int = 50
    ) -> list:
        """Get audit entries for a specific user."""
        return (
            db.query(AuditLog)
            .filter(AuditLog.user_id == user_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_by_resource(
        self, db: Session, resource: str, resource_id: int
    ) -> list:
        """Get all audit entries for a specific resource."""
        return (
            db.query(AuditLog)
            .filter(
                AuditLog.resource == resource,
                AuditLog.resource_id == resource_id,
            )
            .order_by(AuditLog.created_at.desc())
            .all()
        )

    def get_security_events(self, db: Session, limit: int = 100) -> list:
        """Get security-related audit entries (logins, role changes, etc.)."""
        security_actions = [
            self.LOGIN_SUCCESS, self.LOGIN_FAILED, self.LOGOUT,
            self.USER_CREATED, self.USER_ROLE_CHANGED,
            self.SECRET_ROTATED, self.HISTORY_CLEARED,
        ]
        return (
            db.query(AuditLog)
            .filter(AuditLog.action.in_(security_actions))
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .all()
        )

    def serialize(self, entry: AuditLog) -> dict:
        """Convert an AuditLog entry to a JSON-safe dict."""
        return {
            "id":          entry.id,
            "user_id":     entry.user_id,
            "username":    entry.username,
            "action":      entry.action,
            "resource":    entry.resource,
            "resource_id": entry.resource_id,
            "details":     entry.details,
            "ip_address":  entry.ip_address,
            "status":      entry.status,
            "created_at":  str(entry.created_at),
        }


# ── Singleton ────────────────────────────────────────────
audit_trail = AuditTrail()
