from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from datetime import datetime, timezone, timedelta
from backend.database import Base

IST = timezone(timedelta(hours=5, minutes=30))

class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    username        = Column(String(50),  unique=True, index=True, nullable=False)
    email           = Column(String(100), unique=True, index=True, nullable=False)
    full_name       = Column(String(100))
    hashed_password = Column(String(200), nullable=False)
    role            = Column(String(20),  default="deployer")
    is_active       = Column(Boolean,     default=True)
    is_admin        = Column(Boolean,     default=False)
    last_login      = Column(DateTime)
    created_at      = Column(DateTime, default=lambda: datetime.now(IST))
    updated_at      = Column(DateTime, default=lambda: datetime.now(IST))