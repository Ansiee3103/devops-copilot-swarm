import re
from backend.core.logger import get_logger

logger = get_logger("secrets_scanner")

# Standard regex patterns for secrets
SECRET_PATTERNS = {
    "AWS Access Key ID": r"\b(AKIA|ASCA|ASIA)[A-Z0-9]{16}\b",
    "AWS Secret Access Key": r"(?i)aws_secret_access_key\s*[:=]\s*['\"][0-9a-zA-Z\/+]{40}['\"]",
    "Private Key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "Generic API Key / Token": r"(?i)(api[_-]?key|secret|passwd|password|token)\s*[:=]\s*['\"][0-9a-zA-Z\-_]{16,40}['\"]",
    "Slack Webhook": r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[a-zA-Z0-9]+"
}

class SecretsScanner:
    """Pre-flight credential and secret scanner"""
    
    def scan_text(self, text: str) -> list[dict]:
        """Scan a block of text/code for secrets. Returns list of matches."""
        if not text:
            return []
            
        findings = []
        lines = text.split("\n")
        
        for name, pattern in SECRET_PATTERNS.items():
            compiled = re.compile(pattern)
            for idx, line in enumerate(lines):
                match = compiled.search(line)
                if match:
                    findings.append({
                        "secret_type": name,
                        "line_number": idx + 1,
                        "snippet": line[:match.start()].strip() + " [REDACTED SECRET] " + line[match.end():].strip()
                    })
        return findings

secrets_scanner = SecretsScanner()
