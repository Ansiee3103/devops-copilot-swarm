from utils.groq_client import ask_llm
from backend.core.logger import get_logger

logger = get_logger("compliance_service")

COMPLIANCE_FRAMEWORKS = {
    "SOC2": {
        "checks": [
            "Non-root container user",
            "Resource limits defined",
            "Health checks configured",
            "Secrets not in env vars",
            "Image vulnerability scan",
            "Network policies defined",
            "Audit logging enabled",
            "RBAC configured"
        ]
    },
    "ISO27001": {
        "checks": [
            "Access control implemented",
            "Encryption at rest",
            "Encryption in transit",
            "Incident response plan",
            "Backup procedures",
            "Change management process",
            "Vulnerability management"
        ]
    },
    "HIPAA": {
        "checks": [
            "PHI data encrypted",
            "Access logs maintained",
            "Minimum necessary access",
            "Audit controls",
            "Automatic logoff",
            "Unique user identification"
        ]
    },
    "PCI_DSS": {
        "checks": [
            "Cardholder data encrypted",
            "Network segmentation",
            "Vulnerability scanning",
            "Access control measures",
            "Monitoring and testing",
            "Information security policy"
        ]
    }
}

class ComplianceEngine:

    def check_dockerfile(self, dockerfile: str,
                         framework: str = "SOC2") -> dict:
        """Check Dockerfile against compliance framework"""
        checks  = COMPLIANCE_FRAMEWORKS.get(
            framework, COMPLIANCE_FRAMEWORKS["SOC2"]
        )["checks"]

        prompt = f"""
        You are a compliance auditor checking a Dockerfile.
        Framework: {framework}

        Dockerfile:
        {dockerfile[:2000]}

        Check each item and respond with JSON ONLY:
        {{
            "passed": ["list of passed checks"],
            "failed": ["list of failed checks"],
            "warnings": ["list of warnings"],
            "compliance_score": 0-100,
            "critical_issues": ["list of critical issues"],
            "recommendations": ["specific fixes needed"]
        }}
        """

        result = ask_llm(prompt)
        try:
            import json, re
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass

        return {
            "passed":           [],
            "failed":           checks,
            "compliance_score": 0,
            "critical_issues":  ["Could not parse compliance check"],
            "recommendations":  ["Manual review required"]
        }

    def check_k8s_manifest(self, manifest: str,
                           framework: str = "SOC2") -> dict:
        """Check K8s manifest against compliance"""
        prompt = f"""
        You are a Kubernetes security compliance auditor.
        Framework: {framework}

        Manifest:
        {manifest[:2000]}

        Check for compliance and respond with JSON ONLY:
        {{
            "security_context_set": true/false,
            "non_root_user": true/false,
            "resource_limits_set": true/false,
            "readonly_filesystem": true/false,
            "privilege_escalation_disabled": true/false,
            "health_checks_set": true/false,
            "compliance_score": 0-100,
            "critical_issues": [],
            "recommendations": []
        }}
        """

        result = ask_llm(prompt)
        try:
            import json, re
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass

        return {
            "compliance_score": 0,
            "critical_issues":  ["Parse error"],
            "recommendations":  ["Manual review required"]
        }

    def generate_compliance_report(
        self,
        service_name:  str,
        dockerfile:    str,
        k8s_manifest:  str,
        framework:     str = "SOC2"
    ) -> dict:
        """Generate full compliance report"""
        dockerfile_check = self.check_dockerfile(dockerfile, framework)
        k8s_check        = self.check_k8s_manifest(k8s_manifest, framework)

        overall_score = round(
            (dockerfile_check.get("compliance_score", 0) +
             k8s_check.get("compliance_score", 0)) / 2
        )

        return {
            "service_name":     service_name,
            "framework":        framework,
            "overall_score":    overall_score,
            "status":           "COMPLIANT" if overall_score >= 80 else
                               "NEEDS_ATTENTION" if overall_score >= 60 else
                               "NON_COMPLIANT",
            "dockerfile_check": dockerfile_check,
            "k8s_check":        k8s_check,
            "generated_at":     __import__('datetime').datetime.now().isoformat()
        }

compliance_engine = ComplianceEngine()