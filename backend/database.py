import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool
from backend.core.config import settings

Base = declarative_base()

# ── Engine — supports both SQLite and PostgreSQL ──────────
if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args = {"check_same_thread": False, "timeout": 15}
    )
else:
    engine = create_engine(
        settings.DATABASE_URL,
        poolclass     = QueuePool,
        pool_size     = 10,
        max_overflow  = 20,
        pool_pre_ping = True,
        pool_recycle  = 300,
        echo          = settings.DEBUG
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    from backend.models.deployment import Deployment
    from backend.models.user       import User
    from backend.models.audit      import AuditLog
    from backend.services.incident_service import Incident
    from backend.services.scheduler_service import ScheduledDeployment
    os.makedirs("database", exist_ok=True)
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()