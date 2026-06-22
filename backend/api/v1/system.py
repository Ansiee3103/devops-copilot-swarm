from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from backend.core.config import settings
from backend.core.security import require_permission
from backend.database import get_db

router = APIRouter(tags=["System"])
IST    = timezone(timedelta(hours=5, minutes=30))

@router.get("/health")
def health():
    return {
        "status":    "ok",
        "version":   settings.APP_VERSION,
        "env":       settings.APP_ENV,
        "timestamp": datetime.now(IST).isoformat()
    }

@router.get("/api/v1/llm/status")
def llm_status(current_user: dict = Depends(require_permission("read"))):
    from utils.groq_client import get_llm_status
    return get_llm_status()

@router.get("/api/v1/ml/insights")
def ml_insights(
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(require_permission("read"))
):
    """Get AI learning insights"""
    from backend.ml.learning_engine import LearningEngine
    engine = LearningEngine(db)
    return engine.get_insights()

@router.post("/api/v1/ml/retrain")
def retrain_model(
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(require_permission("admin"))
):
    """Manually trigger model retraining"""
    from backend.ml.learning_engine import LearningEngine
    engine = LearningEngine(db)
    return engine.retrain_if_needed()

@router.get("/api/v1/ml/predict")
def predict_risk(
    service_name: str,
    changes:      str,
    current_user: dict = Depends(require_permission("read"))
):
    """Get ML risk prediction for a deployment"""
    from backend.ml.risk_model import risk_model
    return risk_model.predict(service_name, changes)

@router.get("/api/v1/cost/estimate")
def cost_estimate(
    service_name: str,
    replicas:     int   = 2,
    cloud:        str   = "gcp",
    current_user: dict  = Depends(require_permission("read"))
):
    from backend.services.cost_service import cost_service
    return cost_service.estimate_deployment_cost(
        service_name, replicas, cloud=cloud
    )

@router.post("/api/v1/compliance/check")
def compliance_check(
    body:         dict,
    current_user: dict = Depends(require_permission("read"))
):
    from backend.services.compliance_service import compliance_engine
    return compliance_engine.generate_compliance_report(
        service_name  = body.get("service_name", ""),
        dockerfile    = body.get("dockerfile", ""),
        k8s_manifest  = body.get("k8s_manifest", ""),
        framework     = body.get("framework", "SOC2")
    )

@router.get("/api/v1/plugins")
def list_plugins(
    current_user: dict = Depends(require_permission("read"))
):
    from backend.plugins.plugin_manager import plugin_manager
    return plugin_manager.list_plugins()

@router.post("/api/v1/collaborate/review")
def create_review(
    body:         dict,
    current_user: dict = Depends(require_permission("deploy"))
):
    from backend.services.collaboration_service import collaboration_service
    return collaboration_service.create_review(
        deployment_id = body.get("deployment_id"),
        requester     = current_user.get("sub"),
        service_name  = body.get("service_name")
    )

@router.post("/api/v1/collaborate/approve/{deployment_id}")
def approve_deployment(
    deployment_id: int,
    body:          dict,
    current_user:  dict = Depends(require_permission("deploy"))
):
    from backend.services.collaboration_service import collaboration_service
    return collaboration_service.approve(
        deployment_id,
        current_user.get("sub"),
        body.get("comment", "")
    )