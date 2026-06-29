import os
import requests
from backend.core.logger import get_logger

logger = get_logger("pagerduty_client")

def send_pagerduty_alert(
    service_name: str,
    status: str,
    risk_score: float,
    healing_report: str,
    affected: list,
) -> dict:
    """Send alert to PagerDuty using Events V2 API"""
    routing_key = os.getenv("PAGERDUTY_ROUTING_KEY")
    if not routing_key:
        logger.debug("PagerDuty routing key not configured — skipping")
        return {"success": False, "reason": "not configured"}

    severity = "error" if risk_score >= 7.0 else "warning" if risk_score >= 4.0 else "info"
    event_action = "resolve" if status == "healed" else "trigger"

    payload = {
        "routing_key": routing_key,
        "event_action": event_action,
        "dedup_key": f"deployment-swarm-{service_name}",
        "payload": {
            "summary": f"[DevOps Swarm] {service_name} status: {status.upper()}",
            "source": "devops-copilot-swarm",
            "severity": severity,
            "custom_details": {
                "service_name": service_name,
                "status": status,
                "risk_score": risk_score,
                "affected_services": affected,
                "healing_report": healing_report[:1000] if healing_report else "N/A"
            }
        }
    }

    try:
        res = requests.post(
            "https://events.pagerduty.com/v2/enqueue",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        if res.status_code == 202:
            logger.info(f"✅ PagerDuty alert sent for {service_name}")
            return {"success": True, "message": "alert enqueued"}
        else:
            logger.error(f"❌ PagerDuty failed: {res.text}")
            return {"success": False, "error": res.text}
    except Exception as e:
        logger.error(f"❌ PagerDuty exception: {e}")
        return {"success": False, "error": str(e)}
