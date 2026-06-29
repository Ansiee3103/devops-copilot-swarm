"""
DORA Metrics Service — Measures DevOps performance using the four DORA metrics.

Metrics:
  1. Deployment Frequency   — How often you deploy to production
  2. Lead Time for Changes  — Time from commit to production
  3. Change Failure Rate    — % of deployments causing failures
  4. Mean Time to Recovery  — How fast you recover from failures
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import func, and_
from sqlalchemy.orm import Session
from backend.models.deployment import Deployment
from backend.core.logger import get_logger

logger = get_logger("dora_metrics")
IST    = timezone(timedelta(hours=5, minutes=30))

# ── DORA Rating Thresholds (from dora.dev) ───────────────
DORA_RATINGS = {
    "deployment_frequency": {
        "elite":  "Multiple times per day",
        "high":   "Once per day to once per week",
        "medium": "Once per week to once per month",
        "low":    "Less than once per month",
    },
    "lead_time": {
        "elite":  "Less than 1 hour",
        "high":   "Less than 1 day",
        "medium": "Less than 1 week",
        "low":    "More than 1 month",
    },
    "change_failure_rate": {
        "elite":  "0-5%",
        "high":   "5-10%",
        "medium": "10-15%",
        "low":    "More than 15%",
    },
    "mttr": {
        "elite":  "Less than 1 hour",
        "high":   "Less than 1 day",
        "medium": "Less than 1 week",
        "low":    "More than 1 month",
    },
}


class DORAMetricsService:
    """Calculates and tracks all four DORA metrics."""

    def __init__(self, db: Session):
        self.db = db

    # ── 1. Deployment Frequency ──────────────────────────

    def deployment_frequency(self, days: int = 30) -> dict:
        """
        Calculate how often deployments happen.

        Returns
        -------
        dict with daily/weekly counts, rating, and trend.
        """
        cutoff = datetime.now(IST) - timedelta(days=days)
        cutoff_naive = cutoff.replace(tzinfo=None)

        total = (
            self.db.query(func.count(Deployment.id))
            .filter(
                Deployment.created_at >= cutoff_naive,
                Deployment.status.in_(["healed", "deployed"]),
            )
            .scalar()
        )

        daily_avg  = round(total / max(days, 1), 2)
        weekly_avg = round(daily_avg * 7, 2)

        # Rating
        if daily_avg >= 1:
            rating = "elite"
        elif daily_avg >= 1 / 7:
            rating = "high"
        elif daily_avg >= 1 / 30:
            rating = "medium"
        else:
            rating = "low"

        # Daily breakdown for trend chart
        daily_counts = self._daily_breakdown(days)

        return {
            "metric":      "deployment_frequency",
            "total":       total,
            "period_days": days,
            "daily_avg":   daily_avg,
            "weekly_avg":  weekly_avg,
            "rating":      rating,
            "rating_desc": DORA_RATINGS["deployment_frequency"][rating],
            "trend":       daily_counts,
        }

    # ── 2. Lead Time for Changes ─────────────────────────

    def lead_time(self, days: int = 30) -> dict:
        """
        Calculate average time from deployment start to completion.

        Uses created_at → updated_at as a proxy for commit → production.
        """
        cutoff = datetime.now(IST) - timedelta(days=days)
        cutoff_naive = cutoff.replace(tzinfo=None)

        deps = (
            self.db.query(Deployment)
            .filter(
                Deployment.created_at >= cutoff_naive,
                Deployment.status.in_(["healed", "deployed"]),
            )
            .all()
        )

        if not deps:
            return {
                "metric":      "lead_time",
                "avg_minutes":  0,
                "avg_hours":    0,
                "rating":       "low",
                "rating_desc":  DORA_RATINGS["lead_time"]["low"],
                "sample_size":  0,
                "period_days":  days,
            }

        durations = []
        for dep in deps:
            if dep.created_at and dep.updated_at:
                delta = dep.updated_at - dep.created_at
                durations.append(delta.total_seconds())

        avg_seconds = sum(durations) / len(durations) if durations else 0
        avg_minutes = round(avg_seconds / 60, 1)
        avg_hours   = round(avg_seconds / 3600, 2)

        # Rating
        if avg_hours < 1:
            rating = "elite"
        elif avg_hours < 24:
            rating = "high"
        elif avg_hours < 168:  # 1 week
            rating = "medium"
        else:
            rating = "low"

        return {
            "metric":      "lead_time",
            "avg_seconds": round(avg_seconds, 1),
            "avg_minutes": avg_minutes,
            "avg_hours":   avg_hours,
            "rating":      rating,
            "rating_desc": DORA_RATINGS["lead_time"][rating],
            "sample_size": len(durations),
            "period_days": days,
        }

    # ── 3. Change Failure Rate ───────────────────────────

    def change_failure_rate(self, days: int = 30) -> dict:
        """
        Calculate the percentage of deployments that cause failures.

        Failures = status in ('failed', 'blocked', 'rollback_failed').
        """
        cutoff = datetime.now(IST) - timedelta(days=days)
        cutoff_naive = cutoff.replace(tzinfo=None)

        total = (
            self.db.query(func.count(Deployment.id))
            .filter(Deployment.created_at >= cutoff_naive)
            .scalar()
        )

        failures = (
            self.db.query(func.count(Deployment.id))
            .filter(
                Deployment.created_at >= cutoff_naive,
                Deployment.status.in_([
                    "failed", "blocked", "rollback_failed"
                ]),
            )
            .scalar()
        )

        rate = round((failures / total * 100) if total > 0 else 0, 1)

        # Rating
        if rate <= 5:
            rating = "elite"
        elif rate <= 10:
            rating = "high"
        elif rate <= 15:
            rating = "medium"
        else:
            rating = "low"

        return {
            "metric":       "change_failure_rate",
            "total_deploys": total,
            "failures":      failures,
            "rate_pct":      rate,
            "rating":        rating,
            "rating_desc":   DORA_RATINGS["change_failure_rate"][rating],
            "period_days":   days,
        }

    # ── 4. Mean Time to Recovery ─────────────────────────

    def mean_time_to_recovery(self, days: int = 30) -> dict:
        """
        Calculate average time from failure detection to recovery.

        Uses deployments that went from 'failed' to 'healed'.
        """
        cutoff = datetime.now(IST) - timedelta(days=days)
        cutoff_naive = cutoff.replace(tzinfo=None)

        healed_deps = (
            self.db.query(Deployment)
            .filter(
                Deployment.created_at >= cutoff_naive,
                Deployment.status == "healed",
            )
            .all()
        )

        if not healed_deps:
            return {
                "metric":      "mttr",
                "avg_minutes": 0,
                "avg_hours":   0,
                "rating":      "elite",
                "rating_desc": DORA_RATINGS["mttr"]["elite"],
                "incidents":   0,
                "period_days": days,
            }

        # Approximate MTTR: time between deployment creation and healing
        recovery_times = []
        for dep in healed_deps:
            if dep.created_at and dep.updated_at:
                delta = dep.updated_at - dep.created_at
                recovery_times.append(delta.total_seconds())

        avg_seconds = (
            sum(recovery_times) / len(recovery_times)
            if recovery_times else 0
        )
        avg_minutes = round(avg_seconds / 60, 1)
        avg_hours   = round(avg_seconds / 3600, 2)

        # Rating
        if avg_hours < 1:
            rating = "elite"
        elif avg_hours < 24:
            rating = "high"
        elif avg_hours < 168:
            rating = "medium"
        else:
            rating = "low"

        return {
            "metric":      "mttr",
            "avg_seconds": round(avg_seconds, 1),
            "avg_minutes": avg_minutes,
            "avg_hours":   avg_hours,
            "rating":      rating,
            "rating_desc": DORA_RATINGS["mttr"][rating],
            "incidents":   len(recovery_times),
            "period_days": days,
        }

    # ── All Metrics Combined ─────────────────────────────

    def get_all_metrics(self, days: int = 30) -> dict:
        """Get all four DORA metrics in a single response."""
        freq    = self.deployment_frequency(days)
        lead    = self.lead_time(days)
        cfr     = self.change_failure_rate(days)
        mttr    = self.mean_time_to_recovery(days)

        # Overall DORA rating (average of all four)
        rating_scores = {
            "elite": 4, "high": 3, "medium": 2, "low": 1
        }
        ratings = [
            freq["rating"], lead["rating"],
            cfr["rating"], mttr["rating"],
        ]
        avg_score = sum(rating_scores[r] for r in ratings) / 4

        if avg_score >= 3.5:
            overall = "elite"
        elif avg_score >= 2.5:
            overall = "high"
        elif avg_score >= 1.5:
            overall = "medium"
        else:
            overall = "low"

        return {
            "overall_rating": overall,
            "overall_score":  round(avg_score, 1),
            "period_days":    days,
            "metrics": {
                "deployment_frequency": freq,
                "lead_time":           lead,
                "change_failure_rate": cfr,
                "mttr":                mttr,
            },
            "benchmarks": DORA_RATINGS,
            "generated_at": datetime.now(IST).isoformat(),
        }

    # ── Trend Data ───────────────────────────────────────

    def get_trends(self, days: int = 30) -> dict:
        """Get daily trend data for all metrics over the period."""
        daily = self._daily_breakdown(days)

        # Calculate rolling averages
        window = 7  # 7-day rolling average
        rolling_avg = []
        for i in range(len(daily)):
            window_start = max(0, i - window + 1)
            window_data  = daily[window_start:i + 1]
            avg = round(
                sum(d["count"] for d in window_data) / len(window_data), 1
            )
            rolling_avg.append({
                "date":        daily[i]["date"],
                "rolling_avg": avg,
            })

        return {
            "daily_deploys": daily,
            "rolling_avg":   rolling_avg,
            "period_days":   days,
        }

    # ── Helpers ───────────────────────────────────────────

    def _daily_breakdown(self, days: int) -> list:
        """Get daily deployment counts for the given period."""
        result = []
        for i in range(days - 1, -1, -1):
            day = datetime.now(IST) - timedelta(days=i)
            day_start = day.replace(
                hour=0, minute=0, second=0, microsecond=0, tzinfo=None
            )
            day_end = day.replace(
                hour=23, minute=59, second=59, microsecond=999999, tzinfo=None
            )

            count = (
                self.db.query(func.count(Deployment.id))
                .filter(
                    Deployment.created_at >= day_start,
                    Deployment.created_at <= day_end,
                )
                .scalar()
            )

            failures = (
                self.db.query(func.count(Deployment.id))
                .filter(
                    Deployment.created_at >= day_start,
                    Deployment.created_at <= day_end,
                    Deployment.status.in_(["failed", "blocked"]),
                )
                .scalar()
            )

            result.append({
                "date":     day_start.strftime("%Y-%m-%d"),
                "count":    count,
                "failures": failures,
            })

        return result
