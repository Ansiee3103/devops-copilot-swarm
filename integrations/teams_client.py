import os
import requests
import json
from backend.core.logger import get_logger

logger = get_logger("teams_client")

def send_teams_alert(
    service_name: str,
    status: str,
    risk_score: float,
    healing_report: str,
    affected: list,
) -> dict:
    """Send alert notification to Microsoft Teams Channel using webhooks"""
    webhook_url = os.getenv("TEAMS_WEBHOOK_URL")
    if not webhook_url:
        logger.debug("Teams webhook URL not configured — skipping")
        return {"success": False, "reason": "not configured"}

    color = "34A853" if status == "healed" else "EA4335" if status in ("blocked", "failed") else "FBBC05"
    status_emoji = "✅" if status == "healed" else "❌" if status in ("blocked", "failed") else "⚠️"

    payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": color,
        "summary": f"DevOps Copilot Swarm Alert - {service_name}",
        "sections": [{
            "activityTitle": f"{status_emoji} DevOps Copilot Swarm Alert: {service_name.upper()} — {status.upper()}",
            "activitySubtitle": "Autonomous Control Plane Event",
            "facts": [
                {"name": "Service", "value": service_name},
                {"name": "Status", "value": status},
                {"name": "Risk Score", "value": f"{risk_score}/10"},
                {"name": "Affected Services", "value": ", ".join(affected) if affected else "None"}
            ],
            "text": f"**AutoHealer Report Summary:**\n\n{healing_report[:300] if healing_report else 'No healing report available'}",
            "markdown": True
        }]
    }

    try:
        res = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        if res.status_code == 200 or res.text == "1":
            logger.info(f"✅ Microsoft Teams alert sent for {service_name}")
            return {"success": True}
        else:
            logger.error(f"❌ Teams webhook failed: {res.text}")
            return {"success": False, "error": res.text}
    except Exception as e:
        logger.error(f"❌ Teams webhook exception: {e}")
        return {"success": False, "error": str(e)}
