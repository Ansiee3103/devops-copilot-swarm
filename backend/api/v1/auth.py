from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta

from backend.database import get_db
from backend.models.schemas import RegisterRequest, TokenResponse, UserResponse
from backend.repositories.user_repo import UserRepository
from backend.core.security import create_access_token, require_permission
from backend.core.logger import get_logger
from backend.models.audit import AuditLog

router = APIRouter(tags=["Authentication"])
logger = get_logger("auth_api")
IST    = timezone(timedelta(hours=5, minutes=30))

@router.post("/auth/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db:        Session                   = Depends(get_db)
):
    repo = UserRepository(db)
    user = repo.authenticate(form_data.username, form_data.password)

    if not user:
        # Audit failed login
        audit = AuditLog(
            username   = form_data.username,
            action     = "login_failed",
            resource   = "auth",
            status     = "failed",
            created_at = datetime.now(IST)
        )
        db.add(audit)
        db.commit()

        logger.warning(f"Failed login: {form_data.username}")
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    token = create_access_token({
        "sub":     user.username,
        "user_id": user.id,
        "role":    user.role,
        "is_admin": user.is_admin
    })

    # Audit successful login
    audit = AuditLog(
        user_id    = user.id,
        username   = user.username,
        action     = "login",
        resource   = "auth",
        status     = "success",
        created_at = datetime.now(IST)
    )
    db.add(audit)
    db.commit()

    logger.info(f"User logged in: {user.username} (role: {user.role})")

    return {
        "access_token": token,
        "token_type":   "bearer",
        "username":     user.username,
        "full_name":    user.full_name or user.username,
        "role":         user.role,
        "is_admin":     user.is_admin
    }

@router.post("/auth/register")
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    repo = UserRepository(db)

    if repo.get_by_username(request.username):
        raise HTTPException(status_code=400, detail="Username already exists")

    user = repo.create(
        username  = request.username,
        email     = request.email,
        full_name = request.full_name,
        password  = request.password
    )

    logger.info(f"New user registered: {user.username}")
    return {"message": f"User {user.username} created successfully"}

@router.get("/auth/me")
def get_me(
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(require_permission("read"))
):
    repo = UserRepository(db)
    user = repo.get_by_username(current_user.get("sub"))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id":        user.id,
        "username":  user.username,
        "email":     user.email,
        "full_name": user.full_name,
        "role":      user.role,
        "is_admin":  user.is_admin
    }

@router.get("/users")
def get_users(
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(require_permission("manage_users"))
):
    repo  = UserRepository(db)
    users = repo.get_all()
    return [
        {
            "id":       u.id,
            "username": u.username,
            "email":    u.email,
            "role":     u.role,
            "is_admin": u.is_admin
        }
        for u in users
    ]