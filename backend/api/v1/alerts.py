from fastapi import APIRouter, Depends
from integrations.alerts import send_all_alerts
from backend.core.security import require_permission

router = APIRouter(prefix="/api/v1/alerts", tags=["Alerts"])

@router.get("/test")
def test_alerts(current_user: dict = Depends(require_permission("read"))):
    result = send_all_alerts(
        service_name   = "test-service",
        status         = "healed",
        risk_score     = 3.0,
        healing_report = "Test alert from DevOps Copilot Swarm",
        affected       = ["order-service"]
    )
    return result
