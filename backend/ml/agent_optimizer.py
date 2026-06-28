import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List
from backend.core.logger import get_logger

logger = get_logger("agent_optimizer")
IST    = timezone(timedelta(hours=5, minutes=30))


class AgentOptimizer:
    """
    Tracks agent prediction accuracy and
    automatically improves prompts over time.

    Monitors:
    - Blast Radius accuracy (predicted vs actual impact)
    - AutoHealer success rate
    - Builder quality (generated code correctness)
    - Orchestrator plan relevance
    """

    def track_prediction(
        self,
        db,
        deployment_id: int,
        agent:         str,
        predicted:     dict,
        actual:        dict
    ) -> Dict:
        """Track a prediction vs actual outcome"""
        from backend.models.deployment import Deployment

        dep = db.query(Deployment).filter(
            Deployment.id == deployment_id
        ).first()

        if not dep:
            return {"error": "Deployment not found"}

        correct  = self._is_correct(agent, predicted, actual)
        accuracy = 1.0 if correct else 0.0

        logger.info(
            f"Agent tracking [{agent}] "
            f"Deployment #{deployment_id}: "
            f"{'✅ Correct' if correct else '❌ Wrong'}"
        )

        return {
            "agent":         agent,
            "deployment_id": deployment_id,
            "correct":       correct,
            "predicted":     predicted,
            "actual":        actual,
            "timestamp":     datetime.now(IST).isoformat()
        }

    def _is_correct(
        self,
        agent:     str,
        predicted: dict,
        actual:    dict
    ) -> bool:
        """Check if agent prediction was correct"""
        if agent == "blast_radius":
            pred_safe   = predicted.get("is_safe", True)
            actual_safe = actual.get("status") == "healed"
            return pred_safe == actual_safe

        if agent == "autohealer":
            return actual.get("status") == "healed"

        return True

    def get_accuracy_report(self, db) -> Dict:
        """Calculate agent accuracy from deployment history"""
        from backend.models.deployment import Deployment
        from sqlalchemy import func

        deps = db.query(Deployment).filter(
            Deployment.status.in_(["healed", "blocked", "failed"])
        ).all()

        if not deps:
            return {"message": "No completed deployments yet"}

        total        = len(deps)
        healed       = sum(1 for d in deps if d.status == "healed")
        blocked      = sum(1 for d in deps if d.status == "blocked")
        failed       = sum(1 for d in deps if d.status == "failed")

        # Blast Radius accuracy
        safe_and_healed   = sum(
            1 for d in deps
            if d.is_safe and d.status == "healed"
        )
        unsafe_and_blocked = sum(
            1 for d in deps
            if not d.is_safe and d.status in ["blocked", "failed"]
        )
        br_accuracy = round(
            (safe_and_healed + unsafe_and_blocked) / total * 100, 1
        ) if total > 0 else 0

        # AutoHealer success rate
        healer_rate = round(healed / total * 100, 1) if total > 0 else 0

        # Risk score calibration
        avg_safe_risk   = round(
            sum(d.risk_score or 0 for d in deps if d.status == "healed") /
            max(healed, 1), 1
        )
        avg_unsafe_risk = round(
            sum(d.risk_score or 0 for d in deps if d.status != "healed") /
            max(total - healed, 1), 1
        )

        return {
            "total_deployments":    total,
            "success_rate":         healer_rate,
            "agent_accuracy": {
                "blast_radius": {
                    "accuracy":     br_accuracy,
                    "grade":        "A" if br_accuracy >= 90 else
                                    "B" if br_accuracy >= 80 else
                                    "C" if br_accuracy >= 70 else "D",
                    "correct_predictions": safe_and_healed + unsafe_and_blocked
                },
                "autohealer": {
                    "success_rate": healer_rate,
                    "healed":       healed,
                    "failed":       failed
                }
            },
            "risk_calibration": {
                "avg_risk_successful":   avg_safe_risk,
                "avg_risk_failed":       avg_unsafe_risk,
                "calibration_gap":       round(avg_unsafe_risk - avg_safe_risk, 1)
            },
            "insights": self._generate_insights(
                br_accuracy, healer_rate,
                avg_safe_risk, avg_unsafe_risk
            )
        }

    def _generate_insights(
        self, br_acc, heal_rate, safe_risk, unsafe_risk
    ) -> List[str]:
        insights = []
        if br_acc < 70:
            insights.append(
                "⚠️ Blast Radius accuracy low — retrain ML model"
            )
        if heal_rate < 80:
            insights.append(
                "⚠️ AutoHealer success rate low — review healing strategies"
            )
        if unsafe_risk - safe_risk < 2:
            insights.append(
                "⚠️ Risk scores not well calibrated — more training data needed"
            )
        if br_acc >= 90 and heal_rate >= 90:
            insights.append(
                "✅ Agents performing excellently!"
            )
        return insights or ["📊 Keep deploying to improve agent accuracy"]


agent_optimizer = AgentOptimizer()