import json
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from backend.core.logger import get_logger

logger = get_logger("anomaly_detector")
IST    = timezone(timedelta(hours=5, minutes=30))


class AnomalyDetector:
    """
    Detects anomalies in deployment patterns using
    statistical methods and ML models.

    Detects:
    - Unusual deployment frequency spikes
    - Abnormal risk score patterns
    - Service failure clustering
    - Off-hours deployment patterns
    - Cascading failure indicators
    """

    def __init__(self):
        self.baseline   = {}
        self.thresholds = {
            "risk_score":      6.0,
            "failure_rate":    0.3,
            "deploy_freq":     5,    # per hour
            "z_score":         2.5
        }

    def detect_risk_anomaly(
        self,
        recent_scores:  List[float],
        current_score:  float
    ) -> Dict:
        """Detect if current risk score is anomalous"""
        if len(recent_scores) < 5:
            return {
                "is_anomaly": False,
                "reason":     "Insufficient historical data",
                "confidence": 0
            }

        arr    = np.array(recent_scores)
        mean   = np.mean(arr)
        std    = np.std(arr)
        z_score = (current_score - mean) / (std + 1e-9)

        is_anomaly  = abs(z_score) > self.thresholds["z_score"]
        severity    = "critical" if z_score > 3.5 else \
                      "high"     if z_score > 2.5 else \
                      "medium"   if z_score > 1.5 else "low"

        return {
            "is_anomaly":     bool(is_anomaly),
            "z_score":        round(float(z_score), 2),
            "current_score":  current_score,
            "historical_avg": round(float(mean), 2),
            "historical_std": round(float(std), 2),
            "severity":       severity if is_anomaly else "none",
            "confidence":     min(100, int(abs(z_score) * 30)),
            "reason":         f"Risk score {current_score:.1f} is "
                              f"{abs(z_score):.1f}σ from mean {mean:.1f}"
                              if is_anomaly else "Normal risk pattern"
        }

    def detect_frequency_anomaly(
        self,
        hourly_counts: List[int],
        current_count: int
    ) -> Dict:
        """Detect unusual deployment frequency"""
        if len(hourly_counts) < 3:
            return {"is_anomaly": False, "reason": "Insufficient data"}

        arr     = np.array(hourly_counts)
        mean    = np.mean(arr)
        std     = np.std(arr)
        z_score = (current_count - mean) / (std + 1e-9)

        is_spike   = current_count > self.thresholds["deploy_freq"]
        is_anomaly = is_spike or abs(z_score) > self.thresholds["z_score"]

        return {
            "is_anomaly":     bool(is_anomaly),
            "current_count":  current_count,
            "avg_per_hour":   round(float(mean), 1),
            "is_spike":       bool(is_spike),
            "z_score":        round(float(z_score), 2),
            "reason":         f"Deployment spike: {current_count} in 1 hour "
                              f"(avg: {mean:.1f})"
                              if is_anomaly else "Normal frequency"
        }

    def detect_failure_cluster(
        self,
        recent_statuses: List[str],
        window: int = 5
    ) -> Dict:
        """Detect clustering of failures"""
        if len(recent_statuses) < window:
            return {"is_anomaly": False, "reason": "Insufficient data"}

        recent     = recent_statuses[-window:]
        fail_count = sum(1 for s in recent if s in ["failed", "blocked"])
        fail_rate  = fail_count / window

        is_anomaly = fail_rate >= self.thresholds["failure_rate"]

        return {
            "is_anomaly":      is_anomaly,
            "failure_rate":    round(fail_rate * 100, 1),
            "failures_in_window": fail_count,
            "window_size":     window,
            "severity":        "critical" if fail_rate > 0.6 else
                               "high"     if fail_rate > 0.4 else
                               "medium",
            "reason":          f"{fail_count}/{window} recent deployments "
                               f"failed ({fail_rate*100:.0f}%)"
                               if is_anomaly else "Normal failure rate"
        }

    def detect_time_anomaly(self, hour: int, weekday: int) -> Dict:
        """Detect off-hours or high-risk time deployments"""
        is_off_hours = not (9 <= hour <= 18)
        is_friday    = weekday == 4
        is_weekend   = weekday >= 5
        is_midnight  = 0 <= hour <= 4

        anomalies = []
        if is_midnight:
            anomalies.append("Midnight deployment (00:00-04:00)")
        elif is_off_hours:
            anomalies.append(f"Off-hours deployment ({hour:02d}:00)")
        if is_friday:
            anomalies.append("Friday deployment — risky!")
        if is_weekend:
            anomalies.append("Weekend deployment")

        return {
            "is_anomaly":   len(anomalies) > 0,
            "anomalies":    anomalies,
            "is_off_hours": is_off_hours,
            "is_friday":    is_friday,
            "is_weekend":   is_weekend,
            "risk_penalty": sum([
                3 if is_midnight else 1 if is_off_hours else 0,
                2 if is_friday else 0,
                1 if is_weekend else 0
            ])
        }

    def full_analysis(self, db: Session, service_name: str,
                      current_risk: float) -> Dict:
        """Run all anomaly detections and return full report"""
        from backend.models.deployment import Deployment
        from sqlalchemy import func

        now    = datetime.now(IST)
        hour   = now.hour
        day    = now.weekday()

        # Get historical data
        deps = db.query(Deployment)\
                 .filter(Deployment.service_name == service_name)\
                 .order_by(Deployment.created_at.desc())\
                 .limit(50)\
                 .all()

        recent_risks    = [d.risk_score for d in deps if d.risk_score]
        recent_statuses = [d.status for d in deps]

        # Count deploys in last hour (strip tzinfo for comparing with offset-naive column)
        one_hour_ago = (now - timedelta(hours=1)).replace(tzinfo=None)
        hourly_count = db.query(func.count(Deployment.id)).filter(
            Deployment.created_at >= one_hour_ago
        ).scalar()

        # Get historical hourly counts (real data from DB)
        hourly_history = []
        for h in range(8, 0, -1):
            h_start = (now - timedelta(hours=h)).replace(tzinfo=None)
            h_end   = (now - timedelta(hours=h - 1)).replace(tzinfo=None)
            h_count = db.query(func.count(Deployment.id)).filter(
                Deployment.created_at >= h_start,
                Deployment.created_at < h_end,
            ).scalar()
            hourly_history.append(h_count)
        if not any(hourly_history):
            hourly_history = [2, 1, 3, 1, 2, 4, 1, 2]  # fallback seed

        # Run all detections
        risk_anomaly  = self.detect_risk_anomaly(recent_risks, current_risk)
        freq_anomaly  = self.detect_frequency_anomaly(
            hourly_history, hourly_count
        )
        fail_cluster  = self.detect_failure_cluster(recent_statuses)
        time_anomaly  = self.detect_time_anomaly(hour, day)

        # Overall anomaly score
        anomaly_count = sum([
            risk_anomaly["is_anomaly"],
            freq_anomaly["is_anomaly"],
            fail_cluster["is_anomaly"],
            time_anomaly["is_anomaly"]
        ])

        overall = "critical" if anomaly_count >= 3 else \
                  "high"     if anomaly_count == 2 else \
                  "medium"   if anomaly_count == 1 else \
                  "normal"

        return {
            "service_name":    service_name,
            "overall_status":  overall,
            "anomaly_count":   anomaly_count,
            "timestamp":       now.isoformat(),
            "detections": {
                "risk":      risk_anomaly,
                "frequency": freq_anomaly,
                "failures":  fail_cluster,
                "timing":    time_anomaly
            },
            "recommendation":  self._get_recommendation(
                overall, risk_anomaly, freq_anomaly,
                fail_cluster, time_anomaly
            )
        }

    def _get_recommendation(
        self, overall, risk, freq, fail, time
    ) -> str:
        if overall == "critical":
            return "🚨 STOP — Multiple anomalies detected. Do not deploy."
        if overall == "high":
            if fail["is_anomaly"]:
                return "⚠️ Recent failures detected. Investigate before deploying."
            if risk["is_anomaly"]:
                return "⚠️ Unusually high risk. Consider blue-green deployment."
        if overall == "medium":
            if time["is_friday"]:
                return "⚠️ Friday deployment. Ensure rollback plan is ready."
            if time["is_off_hours"]:
                return "⚠️ Off-hours deployment. Ensure on-call is notified."
        return "✅ No anomalies detected. Safe to proceed."


anomaly_detector = AnomalyDetector()
