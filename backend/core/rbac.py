from fastapi import Depends, HTTPException, status
from backend.core.security import oauth2_scheme, decode_token
from backend.core.logger import get_logger

logger = get_logger("rbac")

# ── Role Definitions ──────────────────────────────────────
ROLES = {
    "viewer": {
        "permissions": ["read"],
        "description": "Can view deployments and history"
    },
    "deployer": {
        "permissions": ["read", "deploy"],
        "description": "Can view and trigger deployments"
    },
    "senior_deployer": {
        "permissions": ["read", "deploy", "approve"],
        "description": "Can approve high-risk deployments"
    },
    "admin": {
        "permissions": ["read", "deploy", "approve",
                        "manage_users", "clear_history",
                        "manage_org", "view_billing"],
        "description": "Full access"
    }
}

def check_permission(required: str):
    """Dependency — checks if user has required permission"""
    def dependency(token: str = Depends(oauth2_scheme)):
        payload = decode_token(token)
        if not payload:
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED,
                detail      = "Invalid or expired token"
            )

        role  = payload.get("role", "viewer")
        perms = ROLES.get(role, {}).get("permissions", [])

        if required not in perms:
            raise HTTPException(
                status_code = status.HTTP_403_FORBIDDEN,
                detail      = f"'{required}' permission required. Your role: {role}"
            )

        return payload
    return dependency

def get_current_user(token: str = Depends(oauth2_scheme)):
    """Get current user from token"""
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail      = "Invalid or expired token"
        )
    return payload