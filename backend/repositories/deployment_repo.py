import json
from typing import List, Optional
from sqlalchemy.orm import Session
from backend.models.deployment import Deployment
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

class DeploymentRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(self, service_name: str, repo_url: str, changes: str, deployed_by: int = None) -> Deployment:
        dep = Deployment(
            service_name = service_name,
            repo_url     = repo_url,
            changes      = changes,
            deployed_by  = deployed_by,
            status       = "pending",
            logs         = json.dumps([])
        )
        self.db.add(dep)
        self.db.commit()
        self.db.refresh(dep)
        return dep

    def get_by_id(self, deployment_id: int) -> Optional[Deployment]:
        return self.db.query(Deployment).filter(
            Deployment.id == deployment_id
        ).first()

    def get_all(self, limit: int = 20, offset: int = 0) -> List[Deployment]:
        return self.db.query(Deployment)\
                      .order_by(Deployment.created_at.desc())\
                      .offset(offset)\
                      .limit(limit)\
                      .all()

    def update_status(self, deployment_id: int, status: str) -> Deployment:
        dep = self.get_by_id(deployment_id)
        if dep:
            dep.status     = status
            dep.updated_at = datetime.now(IST)
            self.db.commit()
        return dep

    def add_log(self, deployment_id: int, message: str) -> None:
        dep = self.get_by_id(deployment_id)
        if dep:
            logs = json.loads(dep.logs or "[]")
            logs.append(f"[{datetime.now(IST).strftime('%H:%M:%S')} IST] {message}")
            dep.logs       = json.dumps(logs)
            dep.updated_at = datetime.now(IST)
            self.db.commit()

    def update_risk(self, deployment_id: int, risk_data: dict) -> None:
        dep = self.get_by_id(deployment_id)
        if dep:
            dep.risk_score          = risk_data.get("risk_score", 0)
            dep.is_safe             = risk_data.get("is_safe", False)
            dep.is_critical         = risk_data.get("is_critical", False)
            dep.affected_services   = json.dumps(risk_data.get("affected_services", []))
            dep.downstream_services = json.dumps(risk_data.get("downstream_services", []))
            dep.risk_analysis       = risk_data.get("analysis", "")
            dep.updated_at          = datetime.now(IST)
            self.db.commit()

    def update_build(self, deployment_id: int, language: str, plan: str, files: list) -> None:
        dep = self.get_by_id(deployment_id)
        if dep:
            dep.language          = language
            dep.orchestrator_plan = plan
            dep.generated_files   = json.dumps(files)
            dep.updated_at        = datetime.now(IST)
            self.db.commit()

    def update_healing(self, deployment_id: int, healing_report: str) -> None:
        dep = self.get_by_id(deployment_id)
        if dep:
            dep.healing_report = healing_report
            dep.updated_at     = datetime.now(IST)
            self.db.commit()

    def get_stats(self) -> dict:
        total   = self.db.query(Deployment).count()
        healed  = self.db.query(Deployment).filter(Deployment.status == "healed").count()
        blocked = self.db.query(Deployment).filter(Deployment.status == "blocked").count()
        failed  = self.db.query(Deployment).filter(Deployment.status == "failed").count()

        risks = [r[0] for r in self.db.query(Deployment.risk_score).all() if r[0]]
        avg   = round(sum(risks) / len(risks) if risks else 0, 1)

        return {
            "total_deployments": total,
            "successful":        healed,
            "blocked":           blocked,
            "failed":            failed,
            "avg_risk_score":    avg,
            "success_rate":      round(healed / total * 100 if total else 0, 1)
        }

    def clear_all(self) -> None:
        self.db.query(Deployment).delete()
        self.db.commit()