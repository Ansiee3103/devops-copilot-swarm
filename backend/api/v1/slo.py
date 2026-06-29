from fastapi import APIRouter, Depends, HTTPException, status
from backend.database import get_db
from backend.core.security import require_permission
from backend.services.slo_service import SLOService

router = APIRouter(prefix="/api/v1/slo", tags=["SLOs"])

@router.get("/status")
def get_all_slo_statuses(
    db = Depends(get_db),
    current_user: dict = Depends(require_permission("read"))
):
    service = SLOService(db)
    return service.get_all_slo_statuses()

@router.get("/status/{service_name}")
def get_service_slo_status(
    service_name: str,
    db = Depends(get_db),
    current_user: dict = Depends(require_permission("read"))
):
    service = SLOService(db)
    status = service.get_service_slo_status(service_name)
    return status
