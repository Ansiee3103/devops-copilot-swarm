import json
import subprocess
from typing import Dict, List, Optional
from utils.groq_client import ask_llm
from backend.core.logger import get_logger

logger = get_logger("runbook")

RUNBOOKS = {
    "CrashLoopBackOff": {
        "name":        "Fix CrashLoopBackOff",
        "description": "Restart deployment and check logs",
        "severity":    "high",
        "steps": [
            {
                "name":    "Check logs",
                "command": "kubectl logs {service} --previous --tail=50",
                "safe":    True
            },
            {
                "name":    "Describe pod",
                "command": "kubectl describe pod -l app={service}",
                "safe":    True
            },
            {
                "name":    "Restart deployment",
                "command": "kubectl rollout restart deployment/{service}",
                "safe":    True
            },
            {
                "name":    "Verify rollout",
                "command": "kubectl rollout status deployment/{service}",
                "safe":    True
            }
        ]
    },
    "HighMemory": {
        "name":        "Fix High Memory Usage",
        "description": "Scale up memory limits",
        "severity":    "medium",
        "steps": [
            {
                "name":    "Check current usage",
                "command": "kubectl top pods -l app={service}",
                "safe":    True
            },
            {
                "name":    "Increase memory limit",
                "command": "kubectl set resources deployment {service} --limits=memory=512Mi",
                "safe":    True
            },
            {
                "name":    "Verify changes",
                "command": "kubectl get deployment {service} -o jsonpath='{.spec.template.spec.containers[0].resources}'",
                "safe":    True
            }
        ]
    },
    "ServiceDown": {
        "name":        "Restore Service",
        "description": "Restore a down service to healthy state",
        "severity":    "critical",
        "steps": [
            {
                "name":    "Check pod status",
                "command": "kubectl get pods -l app={service}",
                "safe":    True
            },
            {
                "name":    "Get recent logs",
                "command": "kubectl logs -l app={service} --tail=100",
                "safe":    True
            },
            {
                "name":    "Rollback to last stable",
                "command": "kubectl rollout undo deployment/{service}",
                "safe":    True
            },
            {
                "name":    "Scale to ensure availability",
                "command": "kubectl scale deployment {service} --replicas=2",
                "safe":    True
            },
            {
                "name":    "Verify service health",
                "command": "kubectl rollout status deployment/{service} --timeout=120s",
                "safe":    True
            }
        ]
    },
    "HighRiskDeployment": {
        "name":        "Safe High-Risk Deploy",
        "description": "Deploy high-risk change safely",
        "severity":    "high",
        "steps": [
            {
                "name":    "Scale up current version",
                "command": "kubectl scale deployment {service} --replicas=3",
                "safe":    True
            },
            {
                "name":    "Deploy canary (10%)",
                "command": "kubectl set image deployment/{service}-canary {service}={image}",
                "safe":    True
            },
            {
                "name":    "Monitor for 5 minutes",
                "command": "kubectl top pods -l app={service}",
                "safe":    True
            },
            {
                "name":    "Full rollout if healthy",
                "command": "kubectl set image deployment/{service} {service}={image}",
                "safe":    True
            }
        ]
    }
}

class RunbookEngine:

    def find_runbook(
        self,
        failure_pattern: str,
        service_name:    str
    ) -> Optional[Dict]:
        """Find matching runbook for failure pattern"""
        runbook = RUNBOOKS.get(failure_pattern)
        if not runbook:
            return None

        # Substitute service name into commands
        filled_steps = []
        for step in runbook["steps"]:
            filled_steps.append({
                **step,
                "command": step["command"].format(
                    service = service_name,
                    image   = f"{service_name}:latest"
                )
            })

        return {**runbook, "steps": filled_steps}

    def generate_runbook(
        self,
        service_name:  str,
        failure_type:  str,
        error_context: str
    ) -> Dict:
        """Generate a new runbook using AI"""
        prompt = f"""
You are an expert SRE creating a runbook.

Service: {service_name}
Failure: {failure_type}
Context: {error_context}

Create a step-by-step runbook. Respond ONLY with JSON:
{{
    "name": "Runbook name",
    "steps": [
        {{
            "name": "Step name",
            "command": "exact kubectl command",
            "description": "What this does",
            "expected_output": "What success looks like",
            "safe": true
        }}
    ],
    "estimated_time": "X minutes",
    "rollback_command": "kubectl rollout undo deployment/{service_name}"
}}
"""
        try:
            response = ask_llm(prompt)
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.error(f"Runbook generation failed: {e}")

        return self.find_runbook("ServiceDown", service_name) or {}

    def execute_runbook(
        self,
        runbook:      Dict,
        dry_run:      bool = True
    ) -> Dict:
        """
        Execute runbook steps.
        dry_run=True means only simulate — never run in production without review!
        """
        results = []

        for i, step in enumerate(runbook.get("steps", []), 1):
            if dry_run:
                results.append({
                    "step":    i,
                    "name":    step["name"],
                    "command": step["command"],
                    "status":  "simulated",
                    "output":  f"[DRY RUN] Would execute: {step['command']}"
                })
            else:
                try:
                    result = subprocess.run(
                        step["command"].split(),
                        capture_output = True,
                        text           = True,
                        timeout        = 30
                    )
                    results.append({
                        "step":    i,
                        "name":    step["name"],
                        "command": step["command"],
                        "status":  "success" if result.returncode == 0 else "failed",
                        "output":  result.stdout or result.stderr
                    })
                except Exception as e:
                    results.append({
                        "step":   i,
                        "name":   step["name"],
                        "status": "error",
                        "output": str(e)
                    })

        success_count = sum(1 for r in results if r["status"] in ["success", "simulated"])

        return {
            "runbook_name": runbook.get("name"),
            "total_steps":  len(results),
            "completed":    success_count,
            "dry_run":      dry_run,
            "results":      results,
            "success":      success_count == len(results)
        }

runbook_engine = RunbookEngine()