"""
Rollback Service — Manages deployment rollbacks with version tracking.

Provides manual and automatic rollback capabilities, stores rollback history
in the database, and integrates with the event bus.
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from backend.core.logger import get_logger
from backend.repositories.deployment_repo import DeploymentRepository
from integrations.k8s_client import rollback_deployment, get_service_status

logger = get_logger("rollback_service")
IST    = timezone(timedelta(hours=5, minutes=30))


class RollbackService:
    """Manages deployment rollbacks with history and audit tracking."""

    def __init__(self, db: Session):
        self.db   = db
        self.repo = DeploymentRepository(db)

    def rollback(
        self,
        deployment_id: int,
        reason:        str = "Manual rollback",
        user:          str = "system",
        auto:          bool = False,
    ) -> dict:
        """
        Roll back a deployment to the previous version.

        Parameters
        ----------
        deployment_id : The deployment to roll back.
        reason        : Why the rollback was triggered.
        user          : Who initiated the rollback.
        auto          : Whether this was automatic (health-check failure).

        Returns
        -------
        dict with rollback status, K8s result, and timing info.
        """
        dep = self.repo.get_by_id(deployment_id)
        if not dep:
            return {
                "success": False,
                "message": f"Deployment #{deployment_id} not found",
            }

        service_name = dep.service_name
        prev_status  = dep.status

        logger.info(
            f"🔙 {'Auto-' if auto else ''}Rollback initiated: "
            f"{service_name} (deploy #{deployment_id}) — {reason}"
        )

        # Record rollback start
        self.repo.add_log(
            deployment_id,
            f"🔙 {'Auto-' if auto else ''}Rollback initiated by {user}: {reason}"
        )

        # Execute K8s rollback
        k8s_result = rollback_deployment(service_name)

        if k8s_result["success"]:
            # Update deployment status
            self.repo.update_status(deployment_id, "rolled_back")
            self.repo.add_log(
                deployment_id,
                f"✅ Rollback successful: {k8s_result['message']}"
            )

            # Verify post-rollback health
            post_status = get_service_status(service_name)
            self.repo.add_log(
                deployment_id,
                f"📊 Post-rollback status: "
                f"{post_status.get('ready', 0)}/{post_status.get('replicas', 0)} "
                f"replicas ready"
            )

            # Emit event
            try:
                from backend.services.event_bus import event_bus
                event_bus.emit("deploy.rollback", deployment_id, {
                    "service_name": service_name,
                    "reason":       reason,
                    "user":         user,
                    "auto":         auto,
                    "prev_status":  prev_status,
                    "k8s_status":   post_status,
                })
            except Exception:
                pass

            # Audit trail
            try:
                from backend.core.audit_trail import audit_trail
                from backend.database import SessionLocal
                audit_db = SessionLocal()
                audit_trail.log(
                    db=audit_db,
                    action=audit_trail.DEPLOY_ROLLBACK,
                    username=user,
                    resource="deployment",
                    resource_id=deployment_id,
                    details=json.dumps({
                        "service_name": service_name,
                        "reason":       reason,
                        "auto":         auto,
                    }),
                )
                audit_db.close()
            except Exception:
                pass

            return {
                "success":      True,
                "deployment_id": deployment_id,
                "service_name": service_name,
                "message":      f"Rollback successful for {service_name}",
                "reason":       reason,
                "auto":         auto,
                "prev_status":  prev_status,
                "new_status":   "rolled_back",
                "k8s_result":   k8s_result,
                "post_health":  post_status,
                "timestamp":    datetime.now(IST).isoformat(),
            }

        else:
            self.repo.update_status(deployment_id, "rollback_failed")
            self.repo.add_log(
                deployment_id,
                f"❌ Rollback failed: {k8s_result['message']}"
            )

            return {
                "success":       False,
                "deployment_id": deployment_id,
                "service_name":  service_name,
                "message":       f"Rollback failed: {k8s_result['message']}",
                "reason":        reason,
                "k8s_result":    k8s_result,
                "timestamp":     datetime.now(IST).isoformat(),
            }

    def get_rollback_history(
        self, service_name: str = None, limit: int = 20
    ) -> list:
        """Get rollback history, optionally filtered by service."""
        from backend.models.deployment import Deployment

        query = self.db.query(Deployment).filter(
            Deployment.status.in_(["rolled_back", "rollback_failed"])
        )

        if service_name:
            query = query.filter(
                Deployment.service_name == service_name
            )

        deps = query.order_by(
            Deployment.updated_at.desc()
        ).limit(limit).all()

        return [
            {
                "id":           dep.id,
                "service_name": dep.service_name,
                "status":       dep.status,
                "risk_score":   dep.risk_score or 0,
                "created_at":   str(dep.created_at),
                "updated_at":   str(dep.updated_at),
            }
            for dep in deps
        ]

    def can_rollback(self, deployment_id: int) -> dict:
        """Check if a deployment can be rolled back."""
        dep = self.repo.get_by_id(deployment_id)
        if not dep:
            return {"can_rollback": False, "reason": "Deployment not found"}

        rollbackable = ["deployed", "healed", "failed"]
        if dep.status not in rollbackable:
            return {
                "can_rollback": False,
                "reason": (
                    f"Cannot rollback deployment in '{dep.status}' state. "
                    f"Must be one of: {rollbackable}"
                ),
            }

        return {
            "can_rollback":  True,
            "deployment_id": dep.id,
            "service_name":  dep.service_name,
            "current_status": dep.status,
        }
