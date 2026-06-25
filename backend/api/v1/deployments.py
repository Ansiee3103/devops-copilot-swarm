import asyncio
import json
from sse_starlette.sse import EventSourceResponse
from fastapi import APIRouter, Depends, HTTPException, Request, status
from backend.core.security import require_permission
from backend.database import get_db
from backend.repositories.deployment_repo import DeploymentRepository
from backend.services.deployment_service import DeploymentService
from backend.models.schemas import DeployRequest, DeploymentResponse, DeploymentSummary, StatsResponse
from backend.validators import VALID_SERVICES, validate_deploy_request
from backend.core.cache_manager import cached, invalidate_cache

router = APIRouter(prefix="/api/v1", tags=["Deployments"])

@router.get("/services")
def list_services():
    return {"services": VALID_SERVICES}

@router.post("/deploy")
def deploy(
    req: DeployRequest,
    db = Depends(get_db),
    current_user: dict = Depends(require_permission("deploy")),
):
    try:
        validate_deploy_request(req.service_name, req.repo_url, req.changes)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    service = DeploymentService(db)
    result = service.create_and_start(
        service_name=req.service_name,
        repo_url=req.repo_url,
        changes=req.changes,
        user_id=current_user.get("id"),
    )

    # ✅ Invalidate stats and history cache after deploy
    invalidate_cache("stats")
    invalidate_cache("history")

    return result

@router.get("/history")
@cached(ttl=30, prefix="history")  # ✅ Cache for 30 seconds
def list_history(
    limit: int = 20,
    db = Depends(get_db),
    current_user: dict = Depends(require_permission("read")),
):
    repo = DeploymentRepository(db)
    deps = repo.get_all(limit=limit)
    return [
        {
            "id":           dep.id,
            "service_name": dep.service_name,
            "language":     dep.language,
            "status":       dep.status,
            "risk_score":   dep.risk_score or 0.0,
            "is_critical":  dep.is_critical or False,
            "created_at":   str(dep.created_at),
        }
        for dep in deps
    ]

@router.get("/stats")
@cached(ttl=60, prefix="stats")   # ✅ Cache for 60 seconds
def get_stats(
    db = Depends(get_db),
    current_user: dict = Depends(require_permission("read")),
):
    repo = DeploymentRepository(db)
    return repo.get_stats()

@router.get("/status/{deployment_id}")
def get_status(
    deployment_id: int,
    db = Depends(get_db),
    current_user: dict = Depends(require_permission("read")),
):
    repo = DeploymentRepository(db)
    dep = repo.get_by_id(deployment_id)
    if not dep:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found")

    def _parse_json(val):
        if not val:
            return []
        if isinstance(val, list):
            return val
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return []

    return DeploymentResponse(
        id=dep.id,
        service_name=dep.service_name,
        repo_url=dep.repo_url,
        language=dep.language,
        status=dep.status,
        risk_score=dep.risk_score or 0.0,
        is_safe=dep.is_safe or False,
        is_critical=dep.is_critical or False,
        affected_services=_parse_json(dep.affected_services),
        downstream_services=_parse_json(dep.downstream_services),
        generated_files=_parse_json(dep.generated_files),
        risk_analysis=dep.risk_analysis,
        healing_report=dep.healing_report,
        logs=_parse_json(dep.logs),
        created_at=str(dep.created_at),
        updated_at=str(dep.updated_at),
    )

@router.get("/stream/{deployment_id}")
async def stream_deployment(
    deployment_id: int,
    request:       Request,
    token:         str = None,      # ✅ Accept token as query param
    db             = Depends(get_db)
):
    # Verify token manually
    from backend.core.security import decode_token
    if not token:
        raise HTTPException(status_code=401, detail="Token required")

    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    """Server-Sent Events — real-time deployment updates"""

    async def event_generator():
        last_log_count = 0
        last_status    = None

        while True:
            # Check client disconnected
            if await request.is_disconnected():
                break

            try:
                repo = DeploymentRepository(db)
                dep  = repo.get_by_id(deployment_id)

                if not dep:
                    yield {"event": "error", "data": "Deployment not found"}
                    break

                logs     = json.loads(dep.logs or "[]")
                new_logs = logs[last_log_count:]

                # Send new logs
                for log in new_logs:
                    yield {
                        "event": "log",
                        "data":  json.dumps({"log": log})
                    }
                last_log_count = len(logs)

                # Send status update if changed
                if dep.status != last_status:
                    yield {
                        "event": "status",
                        "data":  json.dumps({
                            "id":          dep.id,
                            "status":      dep.status,
                            "risk_score":  dep.risk_score or 0,
                            "is_safe":     dep.is_safe,
                            "is_critical": dep.is_critical
                        })
                    }
                    last_status = dep.status

                # Stop when done
                if dep.status in ["healed", "blocked", "failed"]:
                    yield {
                        "event": "complete",
                        "data":  json.dumps({"status": dep.status})
                    }
                    break

            except Exception as e:
                yield {"event": "error", "data": str(e)}
                break

            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())