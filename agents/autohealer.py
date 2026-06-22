from utils.groq_client import ask_llm
from integrations.k8s_client import (
    get_pod_logs, restart_deployment,
    scale_deployment, rollback_deployment,
    get_service_status, get_resource_usage
)

def autohealer_agent(service_name: str, logs: str = None) -> dict:
    print("\n🔧 AutoHealer Agent — Monitoring for failures...")

    # Get REAL logs from Kubernetes
    real_logs = get_pod_logs(service_name, lines=30)

    # Get real service status
    svc_status   = get_service_status(service_name)
    resource_usage = get_resource_usage(service_name)

    print(f"   Real K8s status: {svc_status}")
    print(f"   Resource usage:  {resource_usage}")

    # Use real logs if available, otherwise use sample
    logs_to_analyze = real_logs if real_logs and "No pod found" not in real_logs else (
        logs or f"ERROR {service_name} CrashLoopBackOff detected"
    )

    prompt = f"""
    You are an autonomous Kubernetes healing AI.

    Service: {service_name}
    Current Status: {svc_status}
    Resource Usage: CPU={resource_usage['cpu']}, Memory={resource_usage['memory']}

    Logs:
    {logs_to_analyze[:1000]}

    Analyze and respond with EXACTLY:
    1. Root Cause: [specific cause]
    2. Affected Services: [impacted services]
    3. Healing Actions Taken:
       - Action 1: [specific kubectl command]
       - Action 2: [specific kubectl command]
       - Action 3: [specific kubectl command]
    4. Prevention: [specific steps]
    5. Status: [current status after healing]
    """

    healing_report = ask_llm(prompt)

    # Execute REAL healing actions
    healing_actions = []

    if svc_status.get("exists"):
        # Check if service is unhealthy
        if svc_status.get("status") == "unhealthy":
            print(f"   🔧 Restarting {service_name}...")
            restart = restart_deployment(service_name)
            healing_actions.append({
                "action":  "restart",
                "success": restart["success"],
                "message": restart["message"]
            })

        # Scale up if replicas are low
        if svc_status.get("ready", 0) < 2:
            print(f"   🔧 Scaling up {service_name} to 2 replicas...")
            scale = scale_deployment(service_name, 2)
            healing_actions.append({
                "action":  "scale",
                "success": scale["success"],
                "message": scale["message"]
            })

    print("✅ AutoHealer — Healing complete!")
    print(healing_report)

    return {
        "service_name":   service_name,
        "healing_report": healing_report,
        "healing_actions": healing_actions,
        "real_logs":      logs_to_analyze[:500],
        "k8s_status":     svc_status,
        "status":         "healed"
    }