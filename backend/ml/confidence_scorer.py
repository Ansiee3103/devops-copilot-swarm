from typing import Dict
from datetime import datetime, timezone, timedelta
from backend.core.logger import get_logger

logger = get_logger("confidence")
IST    = timezone(timedelta(hours=5, minutes=30))


class ConfidenceScorer:
    """
    Multi-dimensional deployment confidence scoring.
    Replaces binary safe/blocked with a nuanced score.

    Dimensions:
    - Risk Score (from Blast Radius Agent)
    - Time Safety (off-hours penalty)
    - Historical Reliability (past success rate)
    - Change Size (scope of changes)
    - Coverage (test + compliance)
    - Team Readiness (approvals, on-call)
    """

    WEIGHTS = {
        "risk":         0.30,
        "time":         0.15,
        "history":      0.25,
        "change_size":  0.10,
        "coverage":     0.10,
        "team":         0.10
    }

    def score_risk(self, risk_score: float) -> Dict:
        """Convert risk score to confidence dimension"""
        confidence = max(0, 100 - (risk_score * 10))
        return {
            "dimension":  "risk",
            "score":      round(confidence),
            "raw_value":  risk_score,
            "label":      "Excellent" if confidence >= 80 else
                          "Good"      if confidence >= 60 else
                          "Fair"      if confidence >= 40 else
                          "Poor"
        }

    def score_time(self) -> Dict:
        """Score based on deployment timing"""
        now     = datetime.now(IST)
        hour    = now.hour
        weekday = now.weekday()

        if 10 <= hour <= 16 and weekday < 4:
            score, label = 100, "Optimal window"
        elif 9 <= hour <= 18 and weekday < 5:
            score, label = 80, "Business hours"
        elif weekday == 4:
            score, label = 40, "Friday — risky"
        elif weekday >= 5:
            score, label = 50, "Weekend"
        elif 0 <= hour <= 4:
            score, label = 20, "Midnight — very risky"
        else:
            score, label = 60, "Off-hours"

        return {
            "dimension": "time",
            "score":     score,
            "raw_value": f"{hour:02d}:00 {'Mon Tue Wed Thu Fri Sat Sun'.split()[weekday]}",
            "label":     label
        }

    def score_history(
        self,
        recent_statuses: list,
        service_name:    str
    ) -> Dict:
        """Score based on service's deployment history"""
        if not recent_statuses:
            return {
                "dimension": "history",
                "score":     70,
                "label":     "No history"
            }

        success_rate = sum(
            1 for s in recent_statuses[-10:]
            if s == "healed"
        ) / min(len(recent_statuses), 10)

        score = int(success_rate * 100)

        return {
            "dimension":    "history",
            "score":        score,
            "raw_value":    f"{success_rate*100:.0f}% success rate",
            "label":        "Excellent" if score >= 90 else
                            "Good"      if score >= 70 else
                            "Fair"      if score >= 50 else
                            "Poor — high failure rate"
        }

    def score_change_size(self, changes: str) -> Dict:
        """Score based on size and scope of changes"""
        words     = len(changes.split())
        high_risk = ["database", "schema", "migration", "payment",
                     "auth", "security", "breaking", "remove", "delete"]

        risk_words = sum(
            1 for w in high_risk
            if w in changes.lower()
        )

        if risk_words >= 2:
            score, label = 20, "High-risk keywords detected"
        elif risk_words == 1:
            score, label = 50, "Risk keyword present"
        elif words > 50:
            score, label = 60, "Large change scope"
        elif words > 20:
            score, label = 75, "Medium change scope"
        else:
            score, label = 90, "Small focused change"

        return {
            "dimension":  "change_size",
            "score":      score,
            "raw_value":  f"{words} words, {risk_words} risk keywords",
            "label":      label
        }

    def score_coverage(
        self,
        has_dockerfile:  bool = True,
        has_k8s:         bool = True,
        has_pipeline:    bool = True,
        compliance_score: int = 80
    ) -> Dict:
        """Score based on generated artifacts and compliance"""
        artifact_score   = sum([has_dockerfile, has_k8s, has_pipeline]) / 3 * 100
        combined         = (artifact_score * 0.5) + (compliance_score * 0.5)

        return {
            "dimension":  "coverage",
            "score":      int(combined),
            "raw_value":  f"Artifacts: {int(artifact_score)}%, Compliance: {compliance_score}%",
            "label":      "Full coverage" if combined >= 80 else
                          "Partial coverage" if combined >= 60 else
                          "Insufficient coverage"
        }

    def score_team(
        self,
        approvals:      int  = 0,
        required:       int  = 1,
        oncall_notified: bool = False
    ) -> Dict:
        """Score based on team readiness"""
        approval_score = min(100, (approvals / required) * 100) if required > 0 else 100
        oncall_bonus   = 10 if oncall_notified else 0
        score          = min(100, int(approval_score) + oncall_bonus)

        return {
            "dimension":  "team",
            "score":      score,
            "raw_value":  f"{approvals}/{required} approvals",
            "label":      "Approved" if approvals >= required else
                          f"Needs {required - approvals} more approval(s)"
        }

    def calculate(
        self,
        risk_score:      float,
        changes:         str,
        recent_statuses: list,
        service_name:    str,
        approvals:       int = 0
    ) -> Dict:
        """Calculate overall deployment confidence score"""
        dimensions = {
            "risk":        self.score_risk(risk_score),
            "time":        self.score_time(),
            "history":     self.score_history(recent_statuses, service_name),
            "change_size": self.score_change_size(changes),
            "coverage":    self.score_coverage(),
            "team":        self.score_team(approvals)
        }

        # Weighted average
        overall = sum(
            dimensions[k]["score"] * self.WEIGHTS[k]
            for k in self.WEIGHTS
        )
        overall = round(overall)

        # Decision
        if overall >= 80:
            decision, color = "DEPLOY ✅",    "green"
        elif overall >= 60:
            decision, color = "CAUTION ⚠️",  "yellow"
        elif overall >= 40:
            decision, color = "REVIEW ❌",   "orange"
        else:
            decision, color = "BLOCK 🛑",    "red"

        return {
            "overall_score": overall,
            "decision":      decision,
            "color":         color,
            "dimensions":    dimensions,
            "summary":       self._summary(overall, dimensions),
            "weights":       self.WEIGHTS
        }

    def _summary(self, overall: int, dimensions: Dict) -> str:
        weak = [
            k for k, v in dimensions.items()
            if v["score"] < 60
        ]
        if not weak:
            return f"Strong deployment confidence ({overall}/100)"
        return (
            f"Confidence {overall}/100 — "
            f"Weak areas: {', '.join(weak)}"
        )


confidence_scorer = ConfidenceScorer()