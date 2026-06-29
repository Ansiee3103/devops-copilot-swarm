"""
Webhooks API — GitHub webhook receiver for GitOps-style deployments.

Receives GitHub push/PR events and auto-triggers the deployment pipeline.
"""

import hmac
import hashlib
import json
import os
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.core.logger import get_logger
from backend.services.deployment_service import DeploymentService
from backend.validators import VALID_SERVICES

router = APIRouter(prefix="/api/v1/webhooks", tags=["Webhooks"])
logger = get_logger("webhooks")

GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")

# ── Mapping: directory → service name ────────────────────
DIR_TO_SERVICE = {
    "src/frontend":               "frontend",
    "src/checkoutservice":        "checkoutservice",
    "src/cartservice":            "cartservice",
    "src/productcatalogservice":  "productcatalogservice",
    "src/currencyservice":        "currencyservice",
    "src/paymentservice":         "paymentservice",
    "src/shippingservice":        "shippingservice",
    "src/emailservice":           "emailservice",
    "src/recommendationservice":  "recommendationservice",
    "src/adservice":              "adservice",
    "src/loadgenerator":          "loadgenerator",
}


def _verify_signature(payload: bytes, signature: str) -> bool:
    """Verify GitHub webhook HMAC-SHA256 signature."""
    if not GITHUB_WEBHOOK_SECRET:
        return True  # Skip if not configured

    expected = hmac.new(
        GITHUB_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(f"sha256={expected}", signature)


def _extract_services_from_commits(commits: list) -> set:
    """Determine which services were changed from commit file paths."""
    services = set()
    for commit in commits:
        for file_list in [
            commit.get("added", []),
            commit.get("modified", []),
            commit.get("removed", []),
        ]:
            for filepath in file_list:
                for dir_prefix, service_name in DIR_TO_SERVICE.items():
                    if filepath.startswith(dir_prefix):
                        services.add(service_name)
    return services


def _extract_deploy_directives(message: str) -> dict:
    """
    Parse commit message for deployment directives.

    Examples:
      [deploy:canary]   → strategy=canary
      [skip-deploy]     → skip=True
      [deploy:rollback] → rollback=True
    """
    directives = {
        "skip":     False,
        "strategy": None,
        "rollback": False,
    }

    msg_lower = message.lower()

    if "[skip-deploy]" in msg_lower or "[no-deploy]" in msg_lower:
        directives["skip"] = True
    if "[deploy:canary]" in msg_lower:
        directives["strategy"] = "canary"
    if "[deploy:blue-green]" in msg_lower or "[deploy:blue_green]" in msg_lower:
        directives["strategy"] = "blue_green"
    if "[deploy:rollback]" in msg_lower:
        directives["rollback"] = True

    return directives


@router.post("/github")
async def github_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Receive GitHub push events and auto-trigger deployments.

    Features:
    - Verifies HMAC signature
    - Auto-detects changed services from file paths
    - Parses deploy directives from commit messages
    - Only triggers on main branch pushes
    """
    # Verify signature
    payload = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not _verify_signature(payload, signature):
        logger.warning("⚠️ Invalid webhook signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    event_type = request.headers.get("X-GitHub-Event", "")
    data       = json.loads(payload)

    logger.info(f"📥 GitHub webhook: {event_type}")

    # Only process push events to main branch
    if event_type == "push":
        ref = data.get("ref", "")
        if ref != "refs/heads/main":
            return {
                "status":  "skipped",
                "message": f"Not main branch: {ref}",
            }

        commits  = data.get("commits", [])
        repo_url = data.get("repository", {}).get("html_url", "")
        pusher   = data.get("pusher", {}).get("name", "unknown")

        # Check for skip directive in head commit
        head_commit = data.get("head_commit", {})
        head_msg    = head_commit.get("message", "")
        directives  = _extract_deploy_directives(head_msg)

        if directives["skip"]:
            logger.info(f"⏭️ Deployment skipped: [skip-deploy] in commit message")
            return {
                "status":  "skipped",
                "message": "Deployment skipped by commit directive",
            }

        # Detect changed services
        changed_services = _extract_services_from_commits(commits)

        if not changed_services:
            return {
                "status":  "skipped",
                "message": "No service-specific changes detected",
            }

        # Build change description from commit messages
        changes = " | ".join(
            c.get("message", "")[:80] for c in commits[:5]
        )

        # Trigger deployments for each changed service
        results = []
        service = DeploymentService(db)

        for svc_name in changed_services:
            if svc_name not in VALID_SERVICES:
                continue

            try:
                result = service.create_and_start(
                    service_name = svc_name,
                    repo_url     = repo_url,
                    changes      = f"[GitOps] {changes}",
                    user_id      = None,  # System-triggered
                )
                results.append({
                    "service":       svc_name,
                    "deployment_id": result.get("deployment_id"),
                    "status":        "triggered",
                })
                logger.info(
                    f"🚀 GitOps deploy triggered: {svc_name} "
                    f"(by {pusher})"
                )
            except Exception as e:
                results.append({
                    "service": svc_name,
                    "status":  "error",
                    "error":   str(e),
                })
                logger.error(f"GitOps deploy failed for {svc_name}: {e}")

        return {
            "status":      "processed",
            "pusher":      pusher,
            "branch":      ref,
            "services":    list(changed_services),
            "deployments": results,
            "directives":  directives,
        }

    elif event_type == "pull_request":
        action = data.get("action", "")
        pr     = data.get("pull_request", {})
        number = pr.get("number", 0)

        logger.info(f"📥 PR #{number} {action}")

        return {
            "status":  "received",
            "event":   "pull_request",
            "action":  action,
            "pr":      number,
            "message": "PR events logged (auto-deploy on merge to main)",
        }

    elif event_type == "ping":
        return {"status": "pong", "message": "Webhook configured successfully"}

    return {"status": "ignored", "event": event_type}
