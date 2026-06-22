import json
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from backend.core.logger import get_logger
from backend.ml.risk_model import risk_model

logger = get_logger("learning_engine")
IST    = timezone(timedelta(hours=5, minutes=30))

class LearningEngine:
    """
    Continuously learns from deployment outcomes
    to improve risk predictions over time
    """

    def __init__(self, db: Session):
        self.db = db

    def learn_from_deployment(self, deployment_id: int):
        """Learn from a completed deployment"""
        from backend.models.deployment import Deployment
        dep = self.db.query(Deployment).filter(
            Deployment.id == deployment_id
        ).first()

        if not dep or dep.status not in ["healed", "blocked", "failed"]:
            return

        # Get prediction vs actual outcome
        actual_was_risky = dep.status in ["blocked", "failed"]
        predicted_risk   = dep.risk_score or 0
        predicted_risky  = predicted_risk >= 6

        # Log learning event
        outcome = {
            "deployment_id":    dep.id,
            "service_name":     dep.service_name,
            "changes":          dep.changes,
            "predicted_risk":   predicted_risk,
            "predicted_risky":  predicted_risky,
            "actual_status":    dep.status,
            "actual_was_risky": actual_was_risky,
            "correct":          predicted_risky == actual_was_risky,
            "learned_at":       datetime.now(IST).isoformat()
        }

        if outcome["correct"]:
            logger.info(f"✅ Prediction CORRECT for #{dep.id} — {dep.service_name}")
        else:
            logger.warning(
                f"⚠️ Prediction WRONG for #{dep.id} — {dep.service_name} "
                f"(predicted: {predicted_risk}/10, actual: {dep.status})"
            )

        return outcome

    def retrain_if_needed(self, min_new_samples: int = 5) -> dict:
        """Retrain model when enough new data available"""
        from backend.models.deployment import Deployment

        deps = self.db.query(Deployment).filter(
            Deployment.status.in_(["healed", "blocked", "failed"])
        ).all()

        training_data = [
            {
                "service_name":  d.service_name,
                "changes":       d.changes or "",
                "status":        d.status,
                "risk_score":    d.risk_score or 0,
                "prev_failures": 0
            }
            for d in deps
        ]

        if len(training_data) < 10:
            return {
                "retrained": False,
                "reason":    f"Need 10 samples, have {len(training_data)}"
            }

        result = risk_model.train(training_data)

        if result["success"]:
            logger.info(
                f"🧠 Model retrained! "
                f"Accuracy: {result['accuracy']}% "
                f"on {result['samples']} samples"
            )

        return result

    def get_insights(self) -> dict:
        """Get learning insights from deployment history"""
        from backend.models.deployment import Deployment
        from sqlalchemy import func

        deps = self.db.query(Deployment).filter(
            Deployment.status.in_(["healed", "blocked", "failed"])
        ).all()

        if not deps:
            return {"message": "No deployment history yet"}

        # Most risky services
        service_failures = {}
        for d in deps:
            if d.status in ["blocked", "failed"]:
                service_failures[d.service_name] = \
                    service_failures.get(d.service_name, 0) + 1

        # Best deployment times
        hour_success = {}
        for d in deps:
            hour = d.created_at.hour if d.created_at else 0
            if hour not in hour_success:
                hour_success[hour] = {"success": 0, "total": 0}
            hour_success[hour]["total"] += 1
            if d.status == "healed":
                hour_success[hour]["success"] += 1

        best_hours = sorted(
            [
                {
                    "hour":    h,
                    "rate":    round(v["success"] / v["total"] * 100, 1),
                    "total":   v["total"]
                }
                for h, v in hour_success.items()
                if v["total"] >= 2
            ],
            key=lambda x: x["rate"],
            reverse=True
        )[:3]

        return {
            "total_deployments":   len(deps),
            "model_trained":       risk_model.trained,
            "riskiest_services":   dict(sorted(
                service_failures.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]),
            "best_deploy_hours":   best_hours,
            "recommendation":      self._get_recommendation(deps)
        }

    def _get_recommendation(self, deps: list) -> str:
        if not deps:
            return "No data yet"
        success_rate = len([d for d in deps if d.status == "healed"]) / len(deps)
        if success_rate > 0.8:
            return "✅ Deployment health is excellent"
        elif success_rate > 0.6:
            return "⚠️ Consider reviewing high-risk services before deploying"
        else:
            return "❌ High failure rate — review deployment practices"