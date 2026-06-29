import subprocess
import json
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

def run_kubectl(command: list, cluster: str = None) -> dict:
    """Run a kubectl command and return output"""
    args = ["kubectl"]
    if cluster:
        args += ["--context", cluster]
    args += command
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=30
        )
        return {
            "success": result.returncode == 0,
            "output":  result.stdout.strip(),
            "error":   result.stderr.strip()
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "output": "", "error": "Command timed out"}
    except Exception as e:
        return {"success": False, "output": "", "error": str(e)}

def get_all_pods(cluster: str = None) -> list:
    """Get all running pods"""
    result = run_kubectl(["get", "pods", "-o", "json"], cluster=cluster)
    if not result["success"]:
        return []

    try:
        data = json.loads(result["output"])
        pods = []
        for item in data.get("items", []):
            pods.append({
                "name":      item["metadata"]["name"],
                "namespace": item["metadata"].get("namespace", "default"),
                "status":    item["status"]["phase"],
                "ready":     all(
                    c["ready"]
                    for c in item["status"].get("containerStatuses", [])
                ),
                "restarts": sum(
                    c.get("restartCount", 0)
                    for c in item["status"].get("containerStatuses", [])
                ),
                "age": item["metadata"].get("creationTimestamp", "")
            })
        return pods
    except:
        return []

def get_pod_logs(service_name: str, lines: int = 50, cluster: str = None) -> str:
    """Get real logs from a running pod"""
    # Find pod name
    result = run_kubectl([
        "get", "pods",
        "-l", f"app={service_name}",
        "-o", "jsonpath={.items[0].metadata.name}"
    ], cluster=cluster)

    if not result["success"] or not result["output"]:
        return f"No pod found for {service_name}"

    pod_name = result["output"]

    # Get logs
    logs_result = run_kubectl([
        "logs", pod_name,
        "--tail", str(lines)
    ], cluster=cluster)

    return logs_result["output"] or f"No logs available for {pod_name}"

def get_service_status(service_name: str, cluster: str = None) -> dict:
    """Get real status of a specific service"""
    result = run_kubectl([
        "get", "deployment", service_name,
        "-o", "json"
    ], cluster=cluster)

    if not result["success"]:
        return {
            "exists":    False,
            "replicas":  0,
            "ready":     0,
            "status":    "not found"
        }

    try:
        data   = json.loads(result["output"])
        spec   = data.get("spec", {})
        status = data.get("status", {})
        return {
            "exists":            True,
            "replicas":          spec.get("replicas", 0),
            "ready":             status.get("readyReplicas", 0),
            "available":         status.get("availableReplicas", 0),
            "status":            "healthy" if status.get("readyReplicas", 0) > 0 else "unhealthy",
            "observed_generation": status.get("observedGeneration", 0)
        }
    except:
        return {"exists": False, "replicas": 0, "ready": 0, "status": "error"}

def get_cluster_health(cluster: str = None) -> dict:
    """Get overall cluster health"""
    pods   = get_all_pods(cluster=cluster)
    total  = len(pods)
    ready  = sum(1 for p in pods if p["ready"])
    failed = sum(1 for p in pods if p["status"] == "Failed")

    return {
        "total_pods":   total,
        "ready_pods":   ready,
        "failed_pods":  failed,
        "health_score": round((ready / total * 100) if total > 0 else 0, 1),
        "pods":         pods
    }

def restart_deployment(service_name: str, cluster: str = None) -> dict:
    """Restart a deployment"""
    result = run_kubectl([
        "rollout", "restart",
        "deployment", service_name
    ], cluster=cluster)
    return {
        "success": result["success"],
        "message": result["output"] or result["error"]
    }

def scale_deployment(service_name: str, replicas: int, cluster: str = None) -> dict:
    """Scale a deployment"""
    result = run_kubectl([
        "scale", "deployment", service_name,
        f"--replicas={replicas}"
    ], cluster=cluster)
    return {
        "success": result["success"],
        "message": result["output"] or result["error"]
    }

def rollback_deployment(service_name: str, cluster: str = None) -> dict:
    """Rollback a deployment to previous version"""
    result = run_kubectl([
        "rollout", "undo",
        "deployment", service_name
    ], cluster=cluster)
    return {
        "success": result["success"],
        "message": result["output"] or result["error"]
    }

def apply_manifest(manifest_path: str, cluster: str = None) -> dict:
    """Apply a K8s manifest file"""
    result = run_kubectl(["apply", "-f", manifest_path], cluster=cluster)
    return {
        "success": result["success"],
        "message": result["output"] or result["error"]
    }

def get_resource_usage(service_name: str, cluster: str = None) -> dict:
    """Get CPU and memory usage"""
    result = run_kubectl([
        "top", "pod",
        "-l", f"app={service_name}",
        "--no-headers"
    ], cluster=cluster)

    if not result["success"]:
        return {"cpu": "N/A", "memory": "N/A"}

    lines = result["output"].strip().split('\n')
    if lines and lines[0]:
        parts = lines[0].split()
        if len(parts) >= 3:
            return {"cpu": parts[1], "memory": parts[2]}

    return {"cpu": "N/A", "memory": "N/A"}
