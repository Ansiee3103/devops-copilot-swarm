from datetime import datetime, timezone, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session
from backend.services.incident_service import Incident
from backend.core.logger import get_logger

logger = get_logger("slo_service")
IST    = timezone(timedelta(hours=5, minutes=30))

SLO_CONFIGS = {
    "emailservice": {"slo": 99.9, "allowed_downtime_min": 43.2},
    "recommendationservice": {"slo": 99.9, "allowed_downtime_min": 43.2},
    "adservice": {"slo": 99.5, "allowed_downtime_min": 216.0},
    "shippingservice": {"slo": 99.9, "allowed_downtime_min": 43.2},
    "currencyservice": {"slo": 99.9, "allowed_downtime_min": 43.2},
    "paymentservice": {"slo": 99.9, "allowed_downtime_min": 43.2},
    "cartservice": {"slo": 99.9, "allowed_downtime_min": 43.2},
    "checkoutservice": {"slo": 99.9, "allowed_downtime_min": 43.2},
    "frontend": {"slo": 99.9, "allowed_downtime_min": 43.2},
    "productcatalogservice": {"slo": 99.9, "allowed_downtime_min": 43.2},
}

class SLOService:
    """Service for tracking Service Level Objectives (SLOs) and Error Budgets"""
    
    def __init__(self, db: Session):
        self.db = db
        
    def get_service_slo_status(self, service_name: str, days: int = 30) -> dict:
        """Calculate the remaining error budget for a service in minutes and percentage"""
        config = SLO_CONFIGS.get(service_name, {"slo": 99.9, "allowed_downtime_min": 43.2})
        allowed = config["allowed_downtime_min"]
        
        # Query P1 and P2 incidents in the last 'days'
        cutoff = datetime.now(IST) - timedelta(days=days)
        cutoff_naive = cutoff.replace(tzinfo=None)
        
        incidents = (
            self.db.query(Incident)
            .filter(
                Incident.service_name == service_name,
                Incident.severity.in_(["P1", "P2"]),
                Incident.created_at >= cutoff_naive
            )
            .all()
        )
        
        consumed_seconds = 0.0
        for inc in incidents:
            start = inc.created_at
            if inc.resolved_at:
                end = inc.resolved_at
            else:
                end = datetime.now(IST).replace(tzinfo=None)
                
            if start and end:
                consumed_seconds += (end - start).total_seconds()
                
        consumed_minutes = round(consumed_seconds / 60.0, 1)
        remaining_minutes = max(0.0, round(allowed - consumed_minutes, 1))
        
        budget_percent = round((remaining_minutes / allowed) * 100.0, 1) if allowed > 0 else 0.0
        exhausted = consumed_minutes >= allowed
        
        return {
            "service_name": service_name,
            "slo_percentage": config["slo"],
            "allowed_downtime_minutes": allowed,
            "consumed_downtime_minutes": consumed_minutes,
            "remaining_downtime_minutes": remaining_minutes,
            "error_budget_percentage": budget_percent,
            "exhausted": exhausted,
            "incident_count": len(incidents)
        }
        
    def get_all_slo_statuses(self, days: int = 30) -> list[dict]:
        """Get SLO status for all configured services"""
        return [
            self.get_service_slo_status(service, days=days)
            for service in SLO_CONFIGS.keys()
        ]
        
    def check_guardrail(self, service_name: str) -> dict:
        """Helper for deployment pipelines to check if deployment should be blocked"""
        status = self.get_service_slo_status(service_name)
        if status["exhausted"]:
            return {
                "safe": False,
                "reason": f"SLO error budget for '{service_name}' is exhausted ({status['consumed_downtime_minutes']}m downtime vs {status['allowed_downtime_minutes']}m allowed)."
            }
        return {"safe": True, "reason": "SLO error budget is within normal parameters."}
