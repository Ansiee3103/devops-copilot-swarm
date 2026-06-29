"""
Incident Service — Lifecycle management for deployment incidents.

Supports severity levels, escalation policies, timeline tracking,
and auto-creation from failed deployments.
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean
from backend.database import Base
from backend.core.logger import get_logger

logger = get_logger("incident_service")
IST    = timezone(timedelta(hours=5, minutes=30))


# ── Incident Model ───────────────────────────────────────

class Incident(Base):
    __tablename__ = "incidents"

    id              = Column(Integer, primary_key=True, index=True)
    deployment_id   = Column(Integer, index=True)
    service_name    = Column(String(100), nullable=False, index=True)
    title           = Column(String(300), nullable=False)
    description     = Column(Text)
    severity        = Column(String(10), default="P3", index=True)  # P1-P4
    status          = Column(String(30), default="open", index=True)
    assigned_to     = Column(String(100))
    acknowledged_at = Column(DateTime)
    resolved_at     = Column(DateTime)
    resolution      = Column(Text)
    timeline        = Column(Text, default="[]")  # JSON array of events
    risk_score      = Column(Float, default=0.0)
    auto_created    = Column(Boolean, default=False)
    created_at      = Column(DateTime, default=lambda: datetime.now(IST))
    updated_at      = Column(DateTime, default=lambda: datetime.now(IST))


# ── Severity Definitions ─────────────────────────────────

SEVERITY_LEVELS = {
    "P1": {
        "name":         "Critical",
        "description":  "Complete service outage — immediate action required",
        "response_min": 5,
        "escalate_min": 15,
        "notify":       ["slack", "email", "pagerduty"],
    },
    "P2": {
        "name":         "High",
        "description":  "Major feature impaired — respond within 30 minutes",
        "response_min": 30,
        "escalate_min": 60,
        "notify":       ["slack", "email"],
    },
    "P3": {
        "name":         "Medium",
        "description":  "Minor feature impaired — respond within 4 hours",
        "response_min": 240,
        "escalate_min": 480,
        "notify":       ["slack"],
    },
    "P4": {
        "name":         "Low",
        "description":  "Cosmetic issue — respond within 1 business day",
        "response_min": 1440,
        "escalate_min": 2880,
        "notify":       ["email"],
    },
}


class IncidentService:
    """Manages the full lifecycle of deployment incidents."""

    def __init__(self, db: Session):
        self.db = db

    # ── Create ───────────────────────────────────────────

    def create(
        self,
        service_name:  str,
        title:         str,
        description:   str = "",
        severity:      str = "P3",
        deployment_id: Optional[int] = None,
        risk_score:    float = 0.0,
        auto_created:  bool = False,
    ) -> dict:
        """Create a new incident."""
        severity = severity.upper() if severity else "P3"
        if severity not in SEVERITY_LEVELS:
            severity = "P3"

        timeline_entry = {
            "event":     "Incident created",
            "timestamp": datetime.now(IST).isoformat(),
            "auto":      auto_created,
        }

        incident = Incident(
            deployment_id = deployment_id,
            service_name  = service_name,
            title         = title,
            description   = description,
            severity      = severity,
            status        = "open",
            risk_score    = risk_score,
            auto_created  = auto_created,
            timeline      = json.dumps([timeline_entry]),
        )

        self.db.add(incident)
        self.db.commit()
        self.db.refresh(incident)

        logger.info(
            f"🚨 Incident #{incident.id} created: "
            f"[{severity}] {title} ({service_name})"
        )

        # Emit event
        try:
            from backend.services.event_bus import event_bus
            event_bus.incident_created(
                deployment_id or 0, incident.id, severity
            )
        except Exception:
            pass

        return self._serialize(incident)

    # ── Create from Failed Deployment ────────────────────

    def create_from_deployment(
        self, deployment_id: int, service_name: str,
        risk_score: float, error_msg: str = ""
    ) -> dict:
        """Auto-create an incident from a failed deployment."""
        # Determine severity from risk score
        if risk_score >= 8:
            severity = "P1"
        elif risk_score >= 6:
            severity = "P2"
        elif risk_score >= 4:
            severity = "P3"
        else:
            severity = "P4"

        title = (
            f"Deployment failure: {service_name} "
            f"(risk: {risk_score}/10)"
        )
        description = (
            f"Auto-created incident for failed deployment #{deployment_id}.\n"
            f"Service: {service_name}\n"
            f"Risk Score: {risk_score}/10\n"
            f"Error: {error_msg or 'Unknown'}"
        )

        return self.create(
            service_name  = service_name,
            title         = title,
            description   = description,
            severity      = severity,
            deployment_id = deployment_id,
            risk_score    = risk_score,
            auto_created  = True,
        )

    # ── Acknowledge ──────────────────────────────────────

    def acknowledge(self, incident_id: int, user: str) -> dict:
        """Acknowledge an incident."""
        incident = self.db.query(Incident).filter(
            Incident.id == incident_id
        ).first()

        if not incident:
            return {"success": False, "message": "Incident not found"}

        incident.status          = "acknowledged"
        incident.assigned_to     = user
        incident.acknowledged_at = datetime.now(IST)
        incident.updated_at      = datetime.now(IST)

        self._add_timeline(
            incident, f"Acknowledged by {user}"
        )

        self.db.commit()
        logger.info(f"✅ Incident #{incident_id} acknowledged by {user}")
        return self._serialize(incident)

    # ── Resolve ──────────────────────────────────────────

    def resolve(
        self, incident_id: int, user: str, resolution: str = ""
    ) -> dict:
        """Resolve an incident."""
        incident = self.db.query(Incident).filter(
            Incident.id == incident_id
        ).first()

        if not incident:
            return {"success": False, "message": "Incident not found"}

        incident.status      = "resolved"
        incident.resolved_at = datetime.now(IST)
        incident.resolution  = resolution
        incident.updated_at  = datetime.now(IST)

        self._add_timeline(
            incident, f"Resolved by {user}: {resolution}"
        )

        self.db.commit()

        # Calculate resolution time
        if incident.created_at:
            resolution_time = (
                incident.resolved_at - incident.created_at
            ).total_seconds()
        else:
            resolution_time = 0

        logger.info(
            f"✅ Incident #{incident_id} resolved by {user} "
            f"(took {round(resolution_time / 60, 1)} min)"
        )

        result = self._serialize(incident)
        result["resolution_minutes"] = round(resolution_time / 60, 1)

        # Emit event
        try:
            from backend.services.event_bus import event_bus
            event_bus.emit("incident.resolved", incident.deployment_id, {
                "incident_id":       incident_id,
                "resolution_minutes": round(resolution_time / 60, 1),
            })
        except Exception:
            pass

        return result

    # ── Escalate ─────────────────────────────────────────

    def escalate(self, incident_id: int, new_severity: str, reason: str = "") -> dict:
        """Escalate an incident to a higher severity."""
        incident = self.db.query(Incident).filter(
            Incident.id == incident_id
        ).first()

        if not incident:
            return {"success": False, "message": "Incident not found"}

        old_severity     = incident.severity
        incident.severity   = new_severity.upper()
        incident.updated_at = datetime.now(IST)

        self._add_timeline(
            incident,
            f"Escalated from {old_severity} → {new_severity}: {reason}"
        )

        self.db.commit()
        logger.warning(
            f"⬆️ Incident #{incident_id} escalated: "
            f"{old_severity} → {new_severity}"
        )
        return self._serialize(incident)

    # ── List & Query ─────────────────────────────────────

    def get_open(self, limit: int = 50) -> list:
        """Get all open/acknowledged incidents."""
        incidents = (
            self.db.query(Incident)
            .filter(Incident.status.in_(["open", "acknowledged"]))
            .order_by(
                # Sort by severity (P1 first) then by creation time
                Incident.severity.asc(),
                Incident.created_at.desc(),
            )
            .limit(limit)
            .all()
        )
        return [self._serialize(i) for i in incidents]

    def get_all(
        self, limit: int = 50, status: str = None,
        service_name: str = None
    ) -> list:
        """Get incidents with optional filters."""
        query = self.db.query(Incident)
        if status:
            query = query.filter(Incident.status == status)
        if service_name:
            query = query.filter(Incident.service_name == service_name)

        incidents = (
            query.order_by(Incident.created_at.desc())
            .limit(limit)
            .all()
        )
        return [self._serialize(i) for i in incidents]

    def get_by_id(self, incident_id: int) -> Optional[dict]:
        """Get a single incident with full details."""
        incident = self.db.query(Incident).filter(
            Incident.id == incident_id
        ).first()
        if not incident:
            return None
        return self._serialize(incident)

    def get_stats(self) -> dict:
        """Get incident statistics."""
        total    = self.db.query(Incident).count()
        open_    = self.db.query(Incident).filter(Incident.status == "open").count()
        ack      = self.db.query(Incident).filter(Incident.status == "acknowledged").count()
        resolved = self.db.query(Incident).filter(Incident.status == "resolved").count()

        p1 = self.db.query(Incident).filter(Incident.severity == "P1").count()
        p2 = self.db.query(Incident).filter(Incident.severity == "P2").count()

        return {
            "total":        total,
            "open":         open_,
            "acknowledged": ack,
            "resolved":     resolved,
            "by_severity":  {"P1": p1, "P2": p2},
        }

    # ── Helpers ──────────────────────────────────────────

    def _add_timeline(self, incident: Incident, event: str):
        """Add an event to the incident timeline."""
        timeline = json.loads(incident.timeline or "[]")
        timeline.append({
            "event":     event,
            "timestamp": datetime.now(IST).isoformat(),
        })
        incident.timeline = json.dumps(timeline)

    def _serialize(self, incident: Incident) -> dict:
        """Convert Incident to JSON-safe dict."""
        return {
            "id":              incident.id,
            "deployment_id":   incident.deployment_id,
            "service_name":    incident.service_name,
            "title":           incident.title,
            "description":     incident.description,
            "severity":        incident.severity,
            "severity_info":   SEVERITY_LEVELS.get(incident.severity, {}),
            "status":          incident.status,
            "assigned_to":     incident.assigned_to,
            "acknowledged_at": str(incident.acknowledged_at) if incident.acknowledged_at else None,
            "resolved_at":     str(incident.resolved_at) if incident.resolved_at else None,
            "resolution":      incident.resolution,
            "timeline":        json.loads(incident.timeline or "[]"),
            "risk_score":      incident.risk_score,
            "auto_created":    incident.auto_created,
            "created_at":      str(incident.created_at),
            "updated_at":      str(incident.updated_at),
        }
