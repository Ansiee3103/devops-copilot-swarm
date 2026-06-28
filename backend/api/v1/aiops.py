from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.core.rbac import check_permission
from backend.core.logger import get_logger

router = APIRouter(prefix="/api/v1/aiops", tags=["AIOps"])
logger = get_logger("aiops_api")

@router.get("/anomaly/{service_name}")
def detect_anomalies(
    service_name: str,
    risk_score:   float = 5.0,
    db:           Session = Depends(get_db),
    current_user: dict   = Depends(check_permission("read"))
):
    """Detect anomalies for a service"""
    # pyrefly: ignore [missing-import]
    from backend.ml.anomaly_detector import anomaly_detector
    return anomaly_detector.full_analysis(db, service_name, risk_score)

@router.get("/predict/load")
def predict_load(
    hours_ahead:  int  = 1,
    current_user: dict = Depends(check_permission("read"))
):
    """Predict traffic load for next N hours"""
    from backend.ml.predictor import traffic_predictor
    return traffic_predictor.predict_load(hours_ahead)

@router.get("/predict/replicas/{service_name}")
def predict_replicas(
    service_name: str,
    current_user: dict = Depends(check_permission("read"))
):
    """Recommend replica count based on predicted traffic"""
    from backend.ml.predictor import traffic_predictor
    return traffic_predictor.recommend_replicas(service_name)

@router.get("/predict/window")
def deployment_window(
    current_user: dict = Depends(check_permission("read"))
):
    """Find optimal deployment windows in next 24 hours"""
    from backend.ml.predictor import traffic_predictor
    return traffic_predictor.get_deployment_window()

@router.post("/rca/{deployment_id}")
def root_cause_analysis(
    deployment_id: int,
    db:            Session = Depends(get_db),
    current_user:  dict    = Depends(check_permission("read"))
):
    """Run AI root cause analysis on a failed deployment"""
    from backend.ml.root_cause import rca_analyzer
    from backend.models.deployment import Deployment
    import json

    dep = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if not dep:
        raise HTTPException(status_code=404, detail="Deployment not found")

    logs = json.loads(dep.logs or "[]")
    error_logs = [l for l in logs if "error" in l.lower() or "❌" in l]

    return rca_analyzer.ai_root_cause(
        service_name    = dep.service_name,
        error_logs      = error_logs,
        deployment_logs = logs,
        risk_score      = dep.risk_score or 0
    )

@router.get("/runbook/{failure_type}/{service_name}")
def get_runbook(
    failure_type: str,
    service_name: str,
    current_user: dict = Depends(check_permission("read"))
):
    """Get runbook for a failure type"""
    from backend.ml.runbook_engine import runbook_engine
    runbook = runbook_engine.find_runbook(failure_type, service_name)
    if not runbook:
        return runbook_engine.generate_runbook(
            service_name, failure_type, "Unknown failure"
        )
    return runbook

@router.post("/runbook/execute")
def execute_runbook(
    body:         dict,
    current_user: dict = Depends(check_permission("deploy"))
):
    """Execute a runbook (dry_run=True by default)"""
    from backend.ml.runbook_engine import runbook_engine
    runbook = body.get("runbook", {})
    dry_run = body.get("dry_run", True)  # ✅ Safe by default
    return runbook_engine.execute_runbook(runbook, dry_run=dry_run)

@router.post("/confidence")
def deployment_confidence(
    body:         dict,
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(check_permission("read"))
):
    """Calculate deployment confidence score"""
    from backend.ml.confidence_scorer import confidence_scorer
    from backend.models.deployment import Deployment

    service_name = body.get("service_name", "")
    risk_score   = body.get("risk_score", 5.0)
    changes      = body.get("changes", "")
    approvals    = body.get("approvals", 0)

    # Get recent deployment history
    deps = db.query(Deployment)\
             .filter(Deployment.service_name == service_name)\
             .order_by(Deployment.created_at.desc())\
             .limit(10).all()
    recent_statuses = [d.status for d in deps]

    return confidence_scorer.calculate(
        risk_score      = risk_score,
        changes         = changes,
        recent_statuses = recent_statuses,
        service_name    = service_name,
        approvals       = approvals
    )

@router.get("/agents/accuracy")
def agent_accuracy(
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(check_permission("read"))
):
    """Get agent accuracy report"""
    from backend.ml.agent_optimizer import agent_optimizer
    return agent_optimizer.get_accuracy_report(db)