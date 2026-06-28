from utils.groq_client import ask_llm
from backend.core.logger import get_logger
from typing import Dict, List
import json

logger = get_logger("root_cause")

class RootCauseAnalyzer:
    """
    AI-powered root cause analysis for deployment failures.
    Correlates logs, metrics, and patterns to identify
    the actual cause of failures.
    """

    FAILURE_PATTERNS = {
        "OOMKilled": {
            "cause":  "Out of Memory — container exceeded memory limit",
            "fix":    "Increase memory limit or optimize app memory usage",
            "kubectl": "kubectl set resources deployment {service} --limits=memory=512Mi"
        },
        "CrashLoopBackOff": {
            "cause":  "Container repeatedly crashing on startup",
            "fix":    "Check application logs for startup errors",
            "kubectl": "kubectl logs {service} --previous"
        },
        "ImagePullBackOff": {
            "cause":  "Cannot pull Docker image from registry",
            "fix":    "Verify image exists in ECR and credentials are valid",
            "kubectl": "kubectl describe pod -l app={service}"
        },
        "Pending": {
            "cause":  "Pod cannot be scheduled — insufficient resources",
            "fix":    "Scale cluster or reduce resource requests",
            "kubectl": "kubectl describe pod -l app={service}"
        },
        "Error": {
            "cause":  "Container exited with error code",
            "fix":    "Check application logs for runtime errors",
            "kubectl": "kubectl logs -l app={service} --tail=100"
        }
    }

    def analyze_logs(self, logs: List[str], service_name: str) -> Dict:
        """Find known patterns in deployment logs"""
        detected = []

        for log in logs:
            for pattern, info in self.FAILURE_PATTERNS.items():
                if pattern.lower() in log.lower():
                    detected.append({
                        "pattern": pattern,
                        "cause":   info["cause"],
                        "fix":     info["fix"],
                        "kubectl": info["kubectl"].format(
                            service=service_name
                        )
                    })

        return {
            "patterns_found": detected,
            "auto_detected":  len(detected) > 0
        }

    def ai_root_cause(
        self,
        service_name:  str,
        error_logs:    List[str],
        deployment_logs: List[str],
        risk_score:    float
    ) -> Dict:
        """Use LLM for deep root cause analysis"""

        prompt = f"""
You are an expert SRE analyzing a deployment failure.

Service: {service_name}
Risk Score: {risk_score}/10

Error Logs:
{chr(10).join(error_logs[-10:])}

Deployment Logs:
{chr(10).join(deployment_logs[-10:])}

Analyze and respond ONLY with this JSON:
{{
    "root_cause": "Single sentence describing the exact root cause",
    "category": "one of: configuration, dependency, resource, code, network, permission",
    "confidence": 0-100,
    "immediate_actions": ["action 1", "action 2", "action 3"],
    "kubectl_commands": ["command 1", "command 2"],
    "prevention": "How to prevent this in future",
    "estimated_fix_time": "e.g. 5 minutes, 30 minutes, 2 hours",
    "severity": "critical|high|medium|low"
}}
"""
        try:
            response = ask_llm(prompt)
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.error(f"AI RCA failed: {e}")

        return {
            "root_cause":        "Unable to determine automatically",
            "category":          "unknown",
            "confidence":        0,
            "immediate_actions": ["Check logs manually", "Rollback if needed"],
            "kubectl_commands":  [f"kubectl logs -l app={service_name}"],
            "prevention":        "Add better monitoring and alerts",
            "estimated_fix_time": "Unknown",
            "severity":          "high"
        }

    def generate_incident_report(
        self,
        service_name:    str,
        deployment_id:   int,
        rca_result:      Dict,
        healing_actions: List[str]
    ) -> Dict:
        """Generate a structured incident report"""
        from datetime import datetime, timezone, timedelta
        IST = timezone(timedelta(hours=5, minutes=30))
        now = datetime.now(IST)

        return {
            "incident_id":    f"INC-{deployment_id:04d}",
            "service":        service_name,
            "timestamp":      now.isoformat(),
            "severity":       rca_result.get("severity", "high"),
            "root_cause":     rca_result.get("root_cause"),
            "category":       rca_result.get("category"),
            "confidence":     rca_result.get("confidence"),
            "time_to_detect": "< 30 seconds (AutoHealer)",
            "time_to_fix":    rca_result.get("estimated_fix_time"),
            "actions_taken":  healing_actions,
            "prevention":     rca_result.get("prevention"),
            "status":         "resolved"
        }

rca_analyzer = RootCauseAnalyzer()