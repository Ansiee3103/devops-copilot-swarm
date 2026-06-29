import threading
import time
from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import Session
from backend.database import Base, SessionLocal
from backend.core.logger import get_logger

logger = get_logger("scheduler_service")
IST    = timezone(timedelta(hours=5, minutes=30))

# ── Scheduled Deployment Model ───────────────────────────

class ScheduledDeployment(Base):
    __tablename__ = "scheduled_deployments"

    id           = Column(Integer, primary_key=True, index=True)
    service_name = Column(String(100), nullable=False)
    repo_url     = Column(String(500), nullable=False)
    changes      = Column(Text)
    scheduled_at = Column(DateTime, nullable=False)  # Next execution time
    cron_expr    = Column(String(100), nullable=True) # Optional recurring cron
    status       = Column(String(50), default="pending")  # pending, triggered, cancelled
    user_id      = Column(Integer, nullable=True)
    created_at   = Column(DateTime, default=lambda: datetime.now(IST))
    updated_at   = Column(DateTime, default=lambda: datetime.now(IST))


# ── Cron Evaluator Helpers ───────────────────────────────

def check_cron(cron_str: str, dt: datetime) -> bool:
    """
    Check if a datetime matches a cron expression.
    Supports standard 5-field format: minute, hour, day_of_month, month, day_of_week
    """
    fields = cron_str.strip().split()
    if len(fields) != 5:
        return False
        
    def match_field(val: int, pattern: str, is_day_of_week=False) -> bool:
        if pattern == "*":
            return True
        if pattern.startswith("*/"):
            try:
                step = int(pattern[2:])
                return val % step == 0
            except ValueError:
                return False
        if "," in pattern:
            return any(match_field(val, p, is_day_of_week) for p in pattern.split(","))
        if "-" in pattern:
            try:
                start, end = map(int, pattern.split("-"))
                return start <= val <= end
            except ValueError:
                return False
        try:
            return int(pattern) == val
        except ValueError:
            return False
            
    # Python weekday(): Monday is 0, Sunday is 6.
    # Convert Python to Cron weekday (Sunday is 0, Monday is 1...):
    cron_weekday = (dt.weekday() + 1) % 7
    
    return (
        match_field(dt.minute, fields[0]) and
        match_field(dt.hour, fields[1]) and
        match_field(dt.day, fields[2]) and
        match_field(dt.month, fields[3]) and
        match_field(cron_weekday, fields[4], is_day_of_week=True)
    )

def get_next_cron_time(cron_str: str, start_dt: datetime) -> datetime:
    """Find the next datetime matching the cron expression"""
    current = start_dt.replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(10080):  # Search up to 1 week ahead
        if check_cron(cron_str, current):
            return current
        current += timedelta(minutes=1)
    return start_dt + timedelta(days=1)  # Fallback


# ── Scheduler Service ────────────────────────────────────

class SchedulerService:
    def __init__(self):
        self._running = False
        self._thread = None

    def create_schedule(
        self, db: Session, service_name: str, repo_url: str,
        changes: str, scheduled_at: datetime, cron_expr: str = None,
        user_id: int = None
    ) -> ScheduledDeployment:
        """Create a new scheduled deployment task"""
        # If cron is specified, calculate the first run time
        if cron_expr:
            scheduled_at = get_next_cron_time(cron_expr, datetime.now(IST))

        job = ScheduledDeployment(
            service_name = service_name,
            repo_url     = repo_url,
            changes      = changes,
            scheduled_at = scheduled_at.replace(tzinfo=None),
            cron_expr    = cron_expr,
            status       = "pending",
            user_id      = user_id
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        logger.info(f"📅 Scheduled deployment created: #{job.id} for {service_name} at {job.scheduled_at}")
        return job

    def cancel_schedule(self, db: Session, job_id: int) -> bool:
        """Cancel a scheduled deployment"""
        job = db.query(ScheduledDeployment).filter(ScheduledDeployment.id == job_id).first()
        if not job or job.status != "pending":
            return False
        job.status = "cancelled"
        job.updated_at = datetime.now(IST)
        db.commit()
        logger.info(f"🚫 Scheduled deployment #{job_id} cancelled")
        return True

    def get_all(self, db: Session, limit: int = 50) -> list[ScheduledDeployment]:
        """Fetch all scheduled deployments"""
        return db.query(ScheduledDeployment).order_by(ScheduledDeployment.scheduled_at.desc()).limit(limit).all()

    def start(self):
        """Start the background execution worker thread"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("✅ Background Scheduler worker thread started")

    def stop(self):
        """Stop the background execution worker thread"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            logger.info("👋 Background Scheduler worker thread stopped")

    def _run_loop(self):
        while self._running:
            db = SessionLocal()
            try:
                now_ist = datetime.now(IST).replace(tzinfo=None)
                due_jobs = (
                    db.query(ScheduledDeployment)
                    .filter(
                        ScheduledDeployment.status == "pending",
                        ScheduledDeployment.scheduled_at <= now_ist
                    )
                    .all()
                )

                for job in due_jobs:
                    logger.info(f"⏰ Triggering scheduled job #{job.id} for {job.service_name}")
                    
                    if job.cron_expr:
                        # For recurring jobs, compute next schedule
                        next_run = get_next_cron_time(job.cron_expr, datetime.now(IST))
                        job.scheduled_at = next_run.replace(tzinfo=None)
                        job.updated_at = datetime.now(IST)
                    else:
                        job.status = "triggered"
                        job.updated_at = datetime.now(IST)
                    
                    db.commit()

                    # Trigger deployment service
                    from backend.services.deployment_service import DeploymentService
                    deploy_service = DeploymentService(db)
                    deploy_service.create_and_start(
                        service_name = job.service_name,
                        repo_url     = job.repo_url,
                        changes      = f"[SCHEDULED] {job.changes}",
                        user_id      = job.user_id or 1
                    )

            except Exception as e:
                logger.error(f"❌ Scheduler execution loop error: {e}")
            finally:
                db.close()

            # Poll every 10 seconds
            time.sleep(10)

scheduler_service = SchedulerService()
