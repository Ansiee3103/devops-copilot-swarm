from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from datetime import datetime, timezone, timedelta
from backend.database import Base

IST = timezone(timedelta(hours=5, minutes=30))

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(Integer, ForeignKey("users.id"))
    username     = Column(String(50))
    action       = Column(String(100), index=True)
    resource     = Column(String(100))
    resource_id  = Column(Integer)
    details      = Column(Text)
    ip_address   = Column(String(50))
    user_agent   = Column(String(200))
    status       = Column(String(20), default="success")
    created_at   = Column(DateTime, default=lambda: datetime.now(IST), index=True)