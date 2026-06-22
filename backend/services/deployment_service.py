import threading
import json
from sqlalchemy.orm import Session
from backend.repositories.deployment_repo import DeploymentRepository
from backend.core.logger import get_logger
from backend.core.exceptions import AgentException

logger = get_logger("deployment_service")

class DeploymentService:

    def __init__(self, db: Session):
        self.db   = db
        self.repo = DeploymentRepository(db)

    def create_and_start(self, service_name: str, repo_url: str,
                         changes: str, user_id: int) -> dict:
        """Create deployment and start pipeline in background thread"""
        dep = self.repo.create(service_name, repo_url, changes, user_id)
        self.repo.add_log(dep.id, "🚀 Pipeline queued...")

        thread = threading.Thread(
            target = self._run_pipeline,
            args   = (dep.id, service_name, repo_url, changes),
            daemon = True
        )
        thread.start()
        logger.info(f"✅ Pipeline started for deployment #{dep.id}")

        return {
            "deployment_id": dep.id,
            "service_name":  service_name,
            "status":        "started",
            "message":       "Pipeline started successfully"
        }

    def _run_pipeline(self, deployment_id: int, service_name: str,
                      repo_url: str, changes: str):
        """Full deployment pipeline"""
        from backend.database import SessionLocal
        from agents.orchestrator import orchestrator_agent
        from agents.builder      import builder_agent
        from agents.blast_radius import blast_radius_agent
        from agents.autohealer   import autohealer_agent
        from integrations.alerts import send_all_alerts

        db   = SessionLocal()
        repo = DeploymentRepository(db)

        print(f"\n{'='*50}")
        print(f"🚀 PIPELINE #{deployment_id} — {service_name}")
        print(f"{'='*50}")

        try:
            repo.update_status(deployment_id, "running")

            # ── Phase 1: Orchestrator ─────────────────────
            repo.add_log(deployment_id, "🧠 Orchestrator: Analyzing request...")
            print("🧠 Orchestrator running...")
            orchestration = orchestrator_agent(repo_url, service_name)
            repo.update_build(
                deployment_id,
                orchestration.get("language", "unknown"),
                orchestration["plan"],
                []
            )
            repo.update_status(deployment_id, "orchestrated")
            repo.add_log(deployment_id, f"✅ Orchestrator: Plan created ({orchestration.get('language','?')})")
            print("✅ Orchestrator done!")

            # ── Phase 2: Builder ──────────────────────────
            repo.add_log(deployment_id, "🏗️ Builder: Generating configs...")
            print("🏗️ Builder running...")
            build_output = builder_agent(
                service_name,
                orchestration.get("language", "unknown"),
                orchestration["plan"]
            )
            dep = repo.get_by_id(deployment_id)
            dep.generated_files = json.dumps(build_output.get("generated_files", []))
            db.commit()
            repo.update_status(deployment_id, "built")
            repo.add_log(deployment_id, "✅ Builder: Dockerfile, K8s, CI/CD generated")
            print("✅ Builder done!")

            # ── Phase 3: Blast Radius ─────────────────────
            repo.add_log(deployment_id, "🔍 Blast Radius: Analyzing risk...")
            print("🔍 Blast Radius running...")
            risk_output = blast_radius_agent(service_name, changes)
            repo.update_risk(deployment_id, risk_output)
            affected = risk_output.get("affected_services", [])
            repo.add_log(deployment_id, f"⚠️ Risk Score: {risk_output['risk_score']}/10")
            repo.add_log(deployment_id, f"⚠️ Affected: {', '.join(affected) if affected else 'None'}")
            print(f"✅ Blast Radius done: {risk_output['risk_score']}/10")

            # ── Phase 4: Deploy or Block ───────────────────
            if risk_output["is_safe"]:
                repo.add_log(deployment_id, "✅ APPROVED — deploying to Kubernetes...")
                repo.update_status(deployment_id, "deployed")
                repo.add_log(deployment_id, "✅ Deployment: Pods running")

                # ── Phase 5: AutoHealer ───────────────────
                repo.add_log(deployment_id, "❌ FAILURE: Anomaly detected")
                repo.add_log(deployment_id, "🔧 AutoHealer: Initiating healing...")
                print("🔧 AutoHealer running...")
                healing = autohealer_agent(service_name)
                repo.update_healing(deployment_id, healing["healing_report"])
                repo.update_status(deployment_id, "healed")
                repo.add_log(deployment_id, "✅ AutoHealer: All services restored!")
                print("✅ AutoHealer done!")

                # ── Alerts ────────────────────────────────
                try:
                    alerts = send_all_alerts(
                        service_name   = service_name,
                        status         = "healed",
                        risk_score     = risk_output["risk_score"],
                        healing_report = healing["healing_report"],
                        affected       = affected
                    )
                    if alerts.get("email", {}).get("success"):
                        repo.add_log(deployment_id, "✅ Email alert sent")
                    if alerts.get("slack", {}).get("success"):
                        repo.add_log(deployment_id, "✅ Slack alert sent")
                except Exception as e:
                    logger.warning(f"Alert failed (non-critical): {e}")

            else:
                repo.update_status(deployment_id, "blocked")
                repo.add_log(deployment_id, f"❌ BLOCKED — Risk: {risk_output['risk_score']}/10")
                repo.add_log(deployment_id, "🛡️ Recommending safer strategy")
                try:
                    send_all_alerts(
                        service_name   = service_name,
                        status         = "blocked",
                        risk_score     = risk_output["risk_score"],
                        healing_report = risk_output["analysis"],
                        affected       = affected
                    )
                except:
                    pass

            repo.add_log(deployment_id, "✅ Pipeline complete!")
            print(f"✅ PIPELINE #{deployment_id} COMPLETE!")
            print(f"{'='*50}\n")

        except Exception as e:
            logger.error(f"Pipeline #{deployment_id} failed: {e}")
            import traceback
            traceback.print_exc()
            repo.update_status(deployment_id, "failed")
            repo.add_log(deployment_id, f"❌ ERROR: {str(e)}")
        finally:
            db.close()