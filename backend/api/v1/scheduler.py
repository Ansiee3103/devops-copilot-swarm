from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from backend.database import get_db
from backend.core.security import require_permission
from backend.services.scheduler_service import scheduler_service

router = APIRouter(prefix="/api/v1/scheduler", tags=["Scheduler"])

class ScheduleRequest(BaseModel):
    service_name: str
    repo_url: str
    changes: str
    scheduled_at: Optional[str] = None  # ISO format string
    cron_expr: Optional[str] = None

@router.post("/schedule")
def create_schedule(
    req: ScheduleRequest,
    db = Depends(get_db),
    current_user: dict = Depends(require_permission("deploy"))
):
    try:
        scheduled_dt = datetime.now()
        if req.scheduled_at:
            # Parse ISO datetime
            scheduled_dt = datetime.fromisoformat(req.scheduled_at.replace("Z", "+00:00"))
        
        job = scheduler_service.create_schedule(
            db = db,
            service_name = req.service_name,
            repo_url = req.repo_url,
            changes = req.changes,
            scheduled_at = scheduled_dt,
            cron_expr = req.cron_expr,
            user_id = current_user.get("id")
        )
        return {
            "success": True,
            "job_id": job.id,
            "scheduled_at": str(job.scheduled_at),
            "cron_expr": job.cron_expr,
            "status": job.status
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to schedule deployment: {str(e)}"
        )

@router.get("/list")
def list_schedules(
    db = Depends(get_db),
    current_user: dict = Depends(require_permission("read"))
):
    jobs = scheduler_service.get_all(db)
    return [
        {
            "id": job.id,
            "service_name": job.service_name,
            "repo_url": job.repo_url,
            "changes": job.changes,
            "scheduled_at": str(job.scheduled_at),
            "cron_expr": job.cron_expr,
            "status": job.status,
            "created_at": str(job.created_at)
        }
        for job in jobs
    ]

@router.delete("/cancel/{job_id}")
def cancel_schedule(
    job_id: int,
    db = Depends(get_db),
    current_user: dict = Depends(require_permission("deploy"))
):
    success = scheduler_service.cancel_schedule(db, job_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job not found or already executed/cancelled."
        )
    return {"success": True, "message": f"Job #{job_id} cancelled successfully."}
