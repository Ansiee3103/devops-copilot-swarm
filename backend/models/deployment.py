from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, Index, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone, timedelta
from backend.database import Base

IST = timezone(timedelta(hours=5, minutes=30))

class Deployment(Base):
    __tablename__ = "deployments"

    id                  = Column(Integer, primary_key=True, index=True)
    service_name        = Column(String(100), nullable=False, index=True)
    repo_url            = Column(String(500), nullable=False)
    language            = Column(String(50))
    changes             = Column(Text)
    risk_score          = Column(Float,   default=0.0)
    is_safe             = Column(Boolean, default=False)
    is_critical         = Column(Boolean, default=False)
    affected_services   = Column(Text)
    downstream_services = Column(Text)
    status              = Column(String(50), default="pending", index=True)
    orchestrator_plan   = Column(Text)
    risk_analysis       = Column(Text)
    healing_report      = Column(Text)
    generated_files     = Column(Text)
    logs                = Column(Text)
    deployed_by         = Column(Integer, ForeignKey("users.id"))
    created_at          = Column(DateTime, default=lambda: datetime.now(IST))
    updated_at          = Column(DateTime, default=lambda: datetime.now(IST))

    __table_args__ = (
        Index("ix_deployment_status_created", "status", "created_at"),
        Index("ix_deployment_service_status", "service_name", "status"),
    )