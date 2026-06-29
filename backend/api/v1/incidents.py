"""
Incidents API — Incident lifecycle management.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.core.rbac import check_permission
from backend.services.incident_service import IncidentService

router = APIRouter(prefix="/api/v1/incidents", tags=["Incidents"])


@router.get("/")
def list_incidents(
    status:       str     = None,
    service_name: str     = None,
    limit:        int     = 50,
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(check_permission("read")),
):
    """List all incidents with optional filters."""
    service = IncidentService(db)
    return service.get_all(limit=limit, status=status, service_name=service_name)


@router.get("/open")
def list_open_incidents(
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(check_permission("read")),
):
    """Get all open/acknowledged incidents sorted by severity."""
    service = IncidentService(db)
    return service.get_open()


@router.get("/stats")
def incident_stats(
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(check_permission("read")),
):
    """Get incident statistics."""
    service = IncidentService(db)
    return service.get_stats()


@router.get("/{incident_id}")
def get_incident(
    incident_id:  int,
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(check_permission("read")),
):
    """Get a single incident with full timeline."""
    service  = IncidentService(db)
    incident = service.get_by_id(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.post("/")
def create_incident(
    body:         dict,
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(check_permission("deploy")),
):
    """Manually create an incident."""
    service = IncidentService(db)
    return service.create(
        service_name  = body.get("service_name", ""),
        title         = body.get("title", ""),
        description   = body.get("description", ""),
        severity      = body.get("severity", "P3"),
        deployment_id = body.get("deployment_id"),
        risk_score    = body.get("risk_score", 0.0),
    )


@router.post("/{incident_id}/acknowledge")
def acknowledge_incident(
    incident_id:  int,
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(check_permission("deploy")),
):
    """Acknowledge an incident."""
    service = IncidentService(db)
    return service.acknowledge(
        incident_id, current_user.get("sub", "unknown")
    )


@router.post("/{incident_id}/resolve")
def resolve_incident(
    incident_id:  int,
    body:         dict,
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(check_permission("deploy")),
):
    """Resolve an incident with resolution notes."""
    service = IncidentService(db)
    return service.resolve(
        incident_id,
        current_user.get("sub", "unknown"),
        body.get("resolution", ""),
    )


@router.post("/{incident_id}/escalate")
def escalate_incident(
    incident_id:  int,
    body:         dict,
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(check_permission("deploy")),
):
    """Escalate an incident to a higher severity."""
    service = IncidentService(db)
    return service.escalate(
        incident_id,
        body.get("severity", "P2"),
        body.get("reason", ""),
    )
