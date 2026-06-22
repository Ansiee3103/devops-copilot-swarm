from fastapi import APIRouter, Depends, HTTPException, Request
from backend.core.security import require_permission

router = APIRouter(prefix="/api/v1/cluster", tags=["Kubernetes"])

@router.get("/health")
def cluster_health(current_user: dict = Depends(require_permission("read"))):
    try:
        from integrations.k8s_client import get_cluster_health
        return get_cluster_health()
    except Exception:
        return {
            "total_pods":   0,
            "ready_pods":   0,
            "failed_pods":  0,
            "health_score": 0,
            "pods":         [],
            "note":         "Kubernetes not available"
        }

@router.get("/pods")
def cluster_pods(current_user: dict = Depends(require_permission("read"))):
    try:
        from integrations.k8s_client import get_all_pods
        return {"pods": get_all_pods()}
    except Exception:
        return {"pods": []}

@router.post("/restart/{service_name}")
def restart_service(
    service_name: str,
    current_user: dict = Depends(require_permission("deploy"))
):
    from integrations.k8s_client import restart_deployment
    return restart_deployment(service_name)

@router.post("/scale/{service_name}/{replicas}")
def scale_service(
    service_name: str,
    replicas:     int,
    current_user: dict = Depends(require_permission("deploy"))
):
    from integrations.k8s_client import scale_deployment
    return scale_deployment(service_name, replicas)

@router.post("/rollback/{service_name}")
def rollback_service(
    service_name: str,
    current_user: dict = Depends(require_permission("deploy"))
):
    from integrations.k8s_client import rollback_deployment
    return rollback_deployment(service_name)

@router.post("/chat")
def chat_with_cluster(
    # pyrefly: ignore [unknown-name]
    request:      Request,
    body:         dict,
    current_user: dict = Depends(require_permission("read"))
):
    """Natural language interface to your cluster"""
    question = body.get("question", "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")

    # Get real cluster data
    try:
        from integrations.k8s_client import get_cluster_health, get_all_pods
        cluster_data = {
            "health": get_cluster_health(),
            "pods":   get_all_pods()[:10]
        }
    except:
        cluster_data = {}

    from backend.ml.cluster_chat import cluster_chat
    result = cluster_chat.ask(question, cluster_data)
    return result