from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean
from datetime import datetime, timezone, timedelta
from backend.database import Base

IST = timezone(timedelta(hours=5, minutes=30))

class DeploymentReview(Base):
    __tablename__ = "deployment_reviews"

    id                = Column(Integer, primary_key=True, index=True)
    deployment_id     = Column(Integer, ForeignKey("deployments.id"), index=True)
    service_name      = Column(String(100))
    requester         = Column(String(50))
    status            = Column(String(20), default="pending")
    required_approvals = Column(Integer, default=2)
    approvals         = Column(Text, default="[]")
    rejections        = Column(Text, default="[]")
    comments          = Column(Text, default="[]")
    created_at        = Column(DateTime, default=lambda: datetime.now(IST))
    updated_at        = Column(DateTime, default=lambda: datetime.now(IST))