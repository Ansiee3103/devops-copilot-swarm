# ── bcrypt 4.x + passlib 1.7.4 compatibility fix ────────────────────────────
# passlib 1.7.4 was never updated for the bcrypt 4.x API change.
# bcrypt 4.x requires bytes for both inputs; passlib may pass str in some paths.
try:
    import bcrypt as _bcrypt_lib
    _orig_checkpw = _bcrypt_lib.checkpw
    def _patched_checkpw(password, hashed):
        if isinstance(password, str):
            password = password.encode("utf-8")
        if isinstance(hashed, str):
            hashed = hashed.encode("utf-8")
        return _orig_checkpw(password, hashed)
    _bcrypt_lib.checkpw = _patched_checkpw
except Exception:
    pass

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from backend.core.config import settings

# ── Password Hashing ──────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

# ── JWT ───────────────────────────────────────────────────
ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

def create_access_token(data: dict) -> str:
    """Create a signed JWT access token with expiry and unique jti."""
    payload = data.copy()
    now     = datetime.now(timezone.utc)
    payload.update({
        "iat": now,
        "exp": now + timedelta(minutes=settings.TOKEN_EXPIRE_MINUTES),
        "jti": str(uuid.uuid4()),
    })
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT token. Returns None if invalid/expired."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None

# ── Role-Based Permissions ────────────────────────────────
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin":    {"read", "deploy", "admin", "manage_users", "clear_history"},
    "deployer": {"read", "deploy", "clear_history"},
    "viewer":   {"read"},
}

def require_permission(permission: str):
    """
    FastAPI dependency factory.
    Usage: current_user: dict = Depends(require_permission("deploy"))
    """
    def dependency(token: str = Depends(oauth2_scheme)) -> dict:
        credentials_exception = HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail      = "Could not validate credentials",
            headers     = {"WWW-Authenticate": "Bearer"},
        )

        if not token:
            raise credentials_exception

        payload = decode_token(token)
        if payload is None:
            raise credentials_exception

        role: str = payload.get("role", "viewer")
        allowed   = ROLE_PERMISSIONS.get(role, set())

        if permission not in allowed:
            raise HTTPException(
                status_code = status.HTTP_403_FORBIDDEN,
                detail      = f"Permission '{permission}' required (your role: {role})"
            )

        return payload

    return dependency