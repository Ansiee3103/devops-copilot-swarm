from typing import Optional, List
from sqlalchemy.orm import Session
from backend.models.user import User
from backend.core.security import hash_password, verify_password
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

class UserRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_username(self, username: str) -> Optional[User]:
        return self.db.query(User).filter(
            User.username == username
        ).first()

    def get_by_id(self, user_id: int) -> Optional[User]:
        return self.db.query(User).filter(
            User.id == user_id
        ).first()

    def get_all(self) -> List[User]:
        return self.db.query(User).all()

    def authenticate(self, username: str, password: str) -> Optional[User]:
        user = self.get_by_username(username)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        user.last_login = datetime.now(IST)
        self.db.commit()
        return user
    
    def create(self, username: str, email: str, full_name: str,
               password: str, role: str = "deployer", is_admin: bool = False) -> User:
        user = User(
            username        = username,
            email           = email,
            full_name       = full_name,
            hashed_password = hash_password(password),
            role            = role,
            is_admin        = is_admin
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def create_admin_if_not_exists(self) -> None:
        if not self.get_by_username("admin"):
            from sqlalchemy.exc import IntegrityError
            try:
                self.create(
                    username  = "admin",
                    email     = "admin@devops-swarm.com",
                    full_name = "System Admin",
                    password  = "admin123",
                    role      = "admin",
                    is_admin  = True
                )
            except IntegrityError:
                self.db.rollback()