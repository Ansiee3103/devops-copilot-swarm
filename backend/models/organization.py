from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from datetime import datetime, timezone, timedelta
from backend.database import Base

IST = timezone(timedelta(hours=5, minutes=30))

class Organization(Base):
    __tablename__ = "organizations"

    id           = Column(Integer, primary_key=True, index=True)
    name         = Column(String(100), unique=True, nullable=False)
    slug         = Column(String(50),  unique=True, nullable=False, index=True)
    email        = Column(String(100), unique=True, nullable=False)
    plan         = Column(String(20),  default="free")    # free/pro/enterprise
    api_key      = Column(String(64),  unique=True, index=True)
    is_active    = Column(Boolean, default=True)
    deploy_limit = Column(Integer, default=10)  # per month
    deploy_count = Column(Integer, default=0)
    created_at   = Column(DateTime, default=lambda: datetime.now(IST))

class Subscription(Base):
    __tablename__ = "subscriptions"

    id              = Column(Integer, primary_key=True)
    org_id          = Column(Integer, nullable=False)
    plan            = Column(String(20))
    status          = Column(String(20), default="active")
    amount_usd      = Column(Integer, default=0)   # in cents
    billing_email   = Column(String(100))
    next_billing_at = Column(DateTime)
    created_at      = Column(DateTime, default=lambda: datetime.now(IST))