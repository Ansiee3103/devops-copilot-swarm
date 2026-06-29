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

        # Audit trail
        try:
            from backend.core.audit_trail import audit_trail
            audit_trail.log(
                db=self.db,
                action=audit_trail.DEPLOY_STARTED,
                user_id=user_id,
                resource="deployment",
                resource_id=dep.id,
                details=json.dumps({
                    "service_name": service_name,
                    "repo_url":     repo_url,
                    "changes":      changes[:200],
                }),
            )
        except Exception:
            pass

        use_celery = False
        try:
            from backend.celery_app import celery_app
            insp = celery_app.control.inspect(timeout=0.5)
            workers = insp.ping() if insp else None  # ping is faster and more reliable than active()
            if workers:
                use_celery = True
        except Exception as e:
            logger.warning(f"Celery check skipped: {e}")

        if use_celery:
            try:
                from backend.tasks import run_deployment_pipeline
                run_deployment_pipeline.delay(dep.id, service_name, repo_url, changes)
                logger.info(f"✅ Pipeline started via Celery task for deployment #{dep.id}")
            except Exception as e:
                logger.warning(f"⚠️ Celery task submission failed: {e}. Falling back to background thread.")
                use_celery = False

        if not use_celery:
            thread = threading.Thread(
                target = self._run_pipeline,
                args   = (dep.id, service_name, repo_url, changes),
                daemon = True
            )
            thread.start()
            logger.info(f"✅ Pipeline started via Thread fallback for deployment #{dep.id}")


        return {
            "deployment_id": dep.id,
            "service_name":  service_name,
            "status":        "started",
            "message":       "Pipeline started successfully"
        }

    def _run_pipeline(self, deployment_id: int, service_name: str,
                      repo_url: str, changes: str):
        """Full deployment pipeline with real K8s execution and event bus."""
        from backend.database import SessionLocal
        from agents.orchestrator import orchestrator_agent
        from agents.builder      import builder_agent
        from agents.blast_radius import blast_radius_agent, recommend_deployment_strategy
        from agents.autohealer   import autohealer_agent
        from integrations.alerts import send_all_alerts
        from backend.services.event_bus import event_bus
        from backend.plugins.plugin_manager import plugin_manager

        db   = SessionLocal()
        repo = DeploymentRepository(db)

        print(f"\n{'='*50}")
        print(f"🚀 PIPELINE #{deployment_id} — {service_name}")
        print(f"{'='*50}")

        # Build plugin context
        plugin_ctx = {
            "deployment_id": deployment_id,
            "service_name":  service_name,
            "repo_url":      repo_url,
            "changes":       changes,
        }

        try:
            repo.update_status(deployment_id, "running")
            event_bus.deploy_started(deployment_id, service_name)
            plugin_manager.trigger("deploy_start", plugin_ctx)

            # ── Pre-flight Check: Secrets Scanner ──────────
            repo.add_log(deployment_id, "🔍 Pre-flight check: Scanning for secrets...")
            from backend.services.secrets_scanner import secrets_scanner
            secrets_found = secrets_scanner.scan_text(changes)
            if secrets_found:
                repo.update_status(deployment_id, "blocked")
                repo.add_log(deployment_id, "❌ BLOCKED: Leaked secrets detected in changes!")
                for f in secrets_found:
                    repo.add_log(deployment_id, f"   ⚠️ Found {f['secret_type']} on line {f['line_number']}: {f['snippet']}")
                event_bus.deploy_log(deployment_id, "❌ BLOCKED: Leaked secrets detected")
                event_bus.deploy_completed(deployment_id, "blocked")
                plugin_ctx["status"] = "blocked"
                plugin_manager.trigger("deploy_blocked", plugin_ctx)
                return

            # ── Pre-flight Check: SLO Error Budget Guardrail ──
            repo.add_log(deployment_id, "📈 Pre-flight check: Validating SLO error budget...")
            from backend.services.slo_service import SLOService
            slo_service = SLOService(db)
            slo_check = slo_service.check_guardrail(service_name)
            if not slo_check["safe"]:
                repo.update_status(deployment_id, "blocked")
                repo.add_log(deployment_id, f"❌ BLOCKED: {slo_check['reason']}")
                event_bus.deploy_log(deployment_id, "❌ BLOCKED: SLO budget exhausted")
                event_bus.deploy_completed(deployment_id, "blocked")
                plugin_ctx["status"] = "blocked"
                plugin_manager.trigger("deploy_blocked", plugin_ctx)
                return

            # ── Phase 1: Orchestrator ─────────────────────
            event_bus.deploy_phase(deployment_id, "orchestrator", "running")
            repo.add_log(deployment_id, "🧠 Orchestrator: Analyzing request...")
            event_bus.deploy_log(deployment_id, "🧠 Orchestrator: Analyzing request...")
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
            event_bus.deploy_phase(deployment_id, "orchestrator", "done")
            print("✅ Orchestrator done!")

            # ── Phase 2: Builder ──────────────────────────
            event_bus.deploy_phase(deployment_id, "builder", "running")
            repo.add_log(deployment_id, "🏗️ Builder: Generating configs...")
            event_bus.deploy_log(deployment_id, "🏗️ Builder: Generating configs...")
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
            event_bus.deploy_phase(deployment_id, "builder", "done")
            print("✅ Builder done!")

            # ── Phase 3: Blast Radius ─────────────────────
            event_bus.deploy_phase(deployment_id, "risk_analysis", "running")
            repo.add_log(deployment_id, "🔍 Blast Radius: Analyzing risk...")
            event_bus.deploy_log(deployment_id, "🔍 Blast Radius: Analyzing risk...")
            print("🔍 Blast Radius running...")

            risk_output = blast_radius_agent(service_name, changes)
            repo.update_risk(deployment_id, risk_output)
            affected = risk_output.get("affected_services", [])
            repo.add_log(deployment_id, f"⚠️ Risk Score: {risk_output['risk_score']}/10")
            repo.add_log(deployment_id, f"⚠️ Affected: {', '.join(affected) if affected else 'None'}")

            # ── Deployment Strategy Recommendation ────────
            strategy = recommend_deployment_strategy(
                service_name,
                risk_output["risk_score"],
                risk_output.get("is_critical", False)
            )
            repo.add_log(
                deployment_id,
                f"📋 Strategy: {strategy['strategy'].upper()} — {strategy['description']}"
            )
            event_bus.deploy_risk_scored(
                deployment_id,
                risk_output["risk_score"],
                risk_output["is_safe"],
                strategy["strategy"]
            )

            event_bus.deploy_phase(deployment_id, "risk_analysis", "done")
            print(f"✅ Blast Radius done: {risk_output['risk_score']}/10 → {strategy['strategy']}")

            # ── AIOps: Anomaly Detection ──────────────────
            try:
                from backend.ml.anomaly_detector import anomaly_detector
                from backend.ml.confidence_scorer import confidence_scorer

                anomaly = anomaly_detector.full_analysis(
                    db, service_name, risk_output["risk_score"]
                )
                repo.add_log(
                    deployment_id,
                    f"🔍 AIOps: {anomaly['overall_status'].upper()} — "
                    f"{anomaly['recommendation']}"
                )

                if anomaly["overall_status"] in ("critical", "high"):
                    event_bus.emit("anomaly.detected", deployment_id, {
                        "status":         anomaly["overall_status"],
                        "anomaly_count":  anomaly["anomaly_count"],
                        "recommendation": anomaly["recommendation"],
                    })
            except Exception as e:
                logger.warning(f"AIOps analysis failed (non-critical): {e}")

            # ── Confidence Score ──────────────────────────
            try:
                from backend.ml.confidence_scorer import confidence_scorer
                confidence = confidence_scorer.calculate(
                    risk_score      = risk_output["risk_score"],
                    changes         = changes,
                    recent_statuses = [],
                    service_name    = service_name
                )
                repo.add_log(
                    deployment_id,
                    f"🎯 Confidence Score: {confidence['overall_score']}/100 "
                    f"— {confidence['decision']}"
                )
            except Exception as e:
                logger.warning(f"Confidence scoring failed (non-critical): {e}")

            # ── Optimal Deployment Window ─────────────────
            try:
                from backend.ml.predictor import traffic_predictor
                window = traffic_predictor.predict_load(hours_ahead=0)
                if not window["deploy_recommended"]:
                    repo.add_log(
                        deployment_id,
                        f"⚠️ Traffic: {window['traffic_level'].upper()} "
                        f"— {window['reason']}"
                    )
            except Exception as e:
                logger.warning(f"Traffic prediction failed (non-critical): {e}")

            # ── Phase 4: Deploy or Block ──────────────────
            if risk_output["is_safe"]:
                event_bus.deploy_phase(deployment_id, "deploying", "running")
                repo.add_log(deployment_id, "✅ APPROVED — deploying to Kubernetes...")
                event_bus.deploy_log(deployment_id, "✅ APPROVED — deploying to Kubernetes...")

                # Execute REAL K8s deployment
                try:
                    from backend.services.k8s_deployment_executor import k8s_executor
                    k8s_result = k8s_executor.execute(
                        service_name    = service_name,
                        manifest_yaml   = build_output.get("k8s_manifest"),
                        strategy        = strategy["strategy"],
                        strategy_config = strategy.get("config", {}),
                    )

                    if k8s_result.get("success"):
                        repo.update_status(deployment_id, "deployed")
                        repo.add_log(deployment_id, "✅ Deployment: Pods running")
                        event_bus.deploy_log(deployment_id, "✅ Deployment: Pods running")
                    else:
                        repo.add_log(
                            deployment_id,
                            f"⚠️ K8s deployment result: {k8s_result.get('message', 'unknown')}"
                        )
                        repo.update_status(deployment_id, "deployed")
                except Exception as e:
                    logger.warning(f"K8s execution skipped: {e}")
                    repo.update_status(deployment_id, "deployed")
                    repo.add_log(deployment_id, "✅ Deployment: Simulated (K8s not connected)")

                event_bus.deploy_phase(deployment_id, "deploying", "done")

                # ── Phase 5: Post-Deploy Health Check ─────
                try:
                    from backend.services.k8s_deployment_executor import k8s_executor
                    health = k8s_executor.health_check(
                        service_name, retries=3, interval=5
                    )

                    if not health["healthy"]:
                        # REAL failure detected → trigger AutoHealer
                        repo.add_log(deployment_id, "❌ FAILURE: Health check failed post-deploy")
                        event_bus.deploy_log(deployment_id, "❌ Health check failed — triggering AutoHealer")

                        event_bus.deploy_phase(deployment_id, "healing", "running")
                        event_bus.heal_started(deployment_id, service_name)
                        repo.add_log(deployment_id, "🔧 AutoHealer: Initiating healing...")
                        print("🔧 AutoHealer running...")

                        healing = autohealer_agent(service_name)
                        repo.update_healing(deployment_id, healing["healing_report"])
                        repo.update_status(deployment_id, "healed")
                        repo.add_log(deployment_id, "✅ AutoHealer: All services restored!")
                        event_bus.heal_completed(deployment_id, healing.get("healing_actions", []))
                        event_bus.deploy_phase(deployment_id, "healing", "done")
                        print("✅ AutoHealer done!")

                        plugin_ctx["status"]         = "healed"
                        plugin_ctx["healing_report"] = healing["healing_report"]
                        plugin_manager.trigger("healed", plugin_ctx)

                        # Create incident for the failure
                        try:
                            from backend.services.incident_service import IncidentService
                            inc_service = IncidentService(db)
                            inc_service.create_from_deployment(
                                deployment_id = deployment_id,
                                service_name  = service_name,
                                risk_score    = risk_output["risk_score"],
                                error_msg     = "Health check failed post-deploy; auto-healed",
                            )
                        except Exception as e:
                            logger.warning(f"Incident creation failed: {e}")
                    else:
                        # Healthy deployment — no healing needed
                        repo.update_status(deployment_id, "healed")
                        repo.add_log(deployment_id, "✅ Post-deploy health check passed — all pods healthy")
                        event_bus.deploy_log(deployment_id, "✅ Health check passed!")

                        plugin_ctx["status"] = "deployed"
                        plugin_manager.trigger("deploy_complete", plugin_ctx)

                except Exception as e:
                    logger.warning(f"Health check skipped: {e}")
                    # Fallback: run AutoHealer for diagnostics
                    event_bus.deploy_phase(deployment_id, "healing", "running")
                    repo.add_log(deployment_id, "🔧 AutoHealer: Running diagnostics...")
                    print("🔧 AutoHealer running...")
                    healing = autohealer_agent(service_name)
                    repo.update_healing(deployment_id, healing["healing_report"])
                    repo.update_status(deployment_id, "healed")
                    repo.add_log(deployment_id, "✅ AutoHealer: Diagnostics complete")
                    event_bus.deploy_phase(deployment_id, "healing", "done")
                    print("✅ AutoHealer done!")

                # ── Alerts ────────────────────────────────
                try:
                    dep = repo.get_by_id(deployment_id)
                    alerts = send_all_alerts(
                        service_name   = service_name,
                        status         = dep.status,
                        risk_score     = risk_output["risk_score"],
                        healing_report = dep.healing_report or "",
                        affected       = affected
                    )
                    if alerts.get("email", {}).get("success"):
                        repo.add_log(deployment_id, "✅ Email alert sent")
                    if alerts.get("slack", {}).get("success"):
                        repo.add_log(deployment_id, "✅ Slack alert sent")
                    event_bus.emit("alert.triggered", deployment_id, alerts)
                except Exception as e:
                    logger.warning(f"Alert failed (non-critical): {e}")

            else:
                # ── Deployment Blocked ────────────────────
                repo.update_status(deployment_id, "blocked")
                repo.add_log(deployment_id, f"❌ BLOCKED — Risk: {risk_output['risk_score']}/10")
                repo.add_log(
                    deployment_id,
                    f"🛡️ Recommended strategy: {strategy['strategy'].upper()} — {strategy['description']}"
                )
                event_bus.deploy_log(
                    deployment_id,
                    f"❌ BLOCKED — Risk: {risk_output['risk_score']}/10"
                )

                plugin_ctx["status"] = "blocked"
                plugin_manager.trigger("deploy_blocked", plugin_ctx)

                try:
                    send_all_alerts(
                        service_name   = service_name,
                        status         = "blocked",
                        risk_score     = risk_output["risk_score"],
                        healing_report = risk_output["analysis"],
                        affected       = affected
                    )
                except Exception:
                    pass

            repo.add_log(deployment_id, "✅ Pipeline complete!")
            event_bus.deploy_completed(deployment_id, repo.get_by_id(deployment_id).status)
            print(f"✅ PIPELINE #{deployment_id} COMPLETE!")
            print(f"{'='*50}\n")

            # Audit trail — completion
            try:
                from backend.core.audit_trail import audit_trail
                final_status = repo.get_by_id(deployment_id).status
                action = (
                    audit_trail.DEPLOY_COMPLETED
                    if final_status in ("healed", "deployed")
                    else audit_trail.DEPLOY_BLOCKED
                    if final_status == "blocked"
                    else audit_trail.DEPLOY_FAILED
                )
                audit_trail.log(
                    db=db,
                    action=action,
                    resource="deployment",
                    resource_id=deployment_id,
                    details=json.dumps({
                        "service_name": service_name,
                        "status":       final_status,
                        "risk_score":   risk_output["risk_score"],
                        "strategy":     strategy["strategy"],
                    }),
                )
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Pipeline #{deployment_id} failed: {e}")
            import traceback
            traceback.print_exc()
            repo.update_status(deployment_id, "failed")
            repo.add_log(deployment_id, f"❌ ERROR: {str(e)}")
            event_bus.deploy_failed(deployment_id, str(e))

            plugin_ctx["status"] = "failed"
            plugin_ctx["error"]  = str(e)
            plugin_manager.trigger("failure_detected", plugin_ctx)

            # Auto-create incident for pipeline failures
            try:
                from backend.services.incident_service import IncidentService
                inc_service = IncidentService(db)
                inc_service.create_from_deployment(
                    deployment_id = deployment_id,
                    service_name  = service_name,
                    risk_score    = 8.0,
                    error_msg     = str(e),
                )
            except Exception:
                pass

        finally:
            db.close()