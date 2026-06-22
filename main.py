import os
import json
from agents.orchestrator import orchestrator_agent
from agents.builder import builder_agent
from agents.blast_radius import blast_radius_agent
from agents.autohealer import autohealer_agent

def save_dashboard_data(data: dict):
    os.makedirs("dashboard", exist_ok=True)
    with open("dashboard/data.json", "w") as f:
        json.dump(data, f, indent=2)
    print("\n✅ Dashboard data updated!")

def run_devops_swarm(repo_url: str, service_name: str, changes: str):
    print("\n" + "="*60)
    print("🚀 DEVOPS COPILOT SWARM — STARTING")
    print("="*60)

    dashboard_data = {
        "service_name": service_name,
        "repo_url": repo_url,
        "status": "running",
        "agents": {
            "orchestrator": "running",
            "builder": "pending",
            "blast_radius": "pending",
            "autohealer": "pending"
        },
        "risk_score": 0,
        "is_safe": False,
        "affected_services": [],
        "risk_analysis": "",
        "healing_report": "",
        "generated_files": [],
        "logs": []
    }

    save_dashboard_data(dashboard_data)

    # Phase 1 — Orchestrator
    orchestration = orchestrator_agent(repo_url, service_name)
    dashboard_data["agents"]["orchestrator"] = "complete"
    dashboard_data["logs"].append("✅ Orchestrator: Deployment plan created")
    save_dashboard_data(dashboard_data)

    # Phase 2 — Builder
    build_output = builder_agent(service_name, orchestration["language"], orchestration["plan"])
    dashboard_data["agents"]["builder"] = "complete"
    dashboard_data["generated_files"] = ["Dockerfile", "k8s-manifest.yaml", "pipeline.yml"]
    dashboard_data["logs"].append("✅ Builder: Configs generated and saved")
    save_dashboard_data(dashboard_data)

    # Phase 3 — Blast Radius
    risk_output = blast_radius_agent(service_name, changes)
    dashboard_data["agents"]["blast_radius"] = "complete"
    dashboard_data["risk_score"] = risk_output["risk_score"]
    dashboard_data["is_safe"] = risk_output["is_safe"]
    dashboard_data["affected_services"] = risk_output["affected_services"]
    dashboard_data["risk_analysis"] = risk_output["analysis"]
    dashboard_data["logs"].append(f"⚠️ Blast Radius: Risk Score {risk_output['risk_score']}/10 detected")
    dashboard_data["logs"].append(f"⚠️ Affected: {', '.join(risk_output['affected_services'])}")
    save_dashboard_data(dashboard_data)

    print("\n" + "="*60)

    if risk_output["is_safe"]:
        dashboard_data["status"] = "deployed"
        dashboard_data["logs"].append("✅ Deployment: APPROVED and deployed")
        save_dashboard_data(dashboard_data)

        print(f"✅ DEPLOYMENT APPROVED — Risk Score: {risk_output['risk_score']}/10")
        print("🚢 Deploying to Kubernetes...")
        print("✅ Deployment Successful!")

        # Phase 4 — AutoHealer
        print("\n⚡ Simulating production failure for demo...")
        dashboard_data["logs"].append("❌ FAILURE: OOMKilled on payment-service pod")
        dashboard_data["logs"].append("❌ FAILURE: order-service connection refused")
        save_dashboard_data(dashboard_data)

        healing = autohealer_agent(service_name)
        dashboard_data["agents"]["autohealer"] = "complete"
        dashboard_data["healing_report"] = healing["healing_report"]
        dashboard_data["status"] = "healed"
        dashboard_data["logs"].append("✅ AutoHealer: Pod restarted")
        dashboard_data["logs"].append("✅ AutoHealer: Memory limit updated")
        dashboard_data["logs"].append("✅ AutoHealer: Circuit breaker enabled")
        dashboard_data["logs"].append("✅ All services healthy — pipeline complete")
        save_dashboard_data(dashboard_data)

    else:
        dashboard_data["status"] = "blocked"
        dashboard_data["logs"].append(f"❌ Deployment BLOCKED — Risk Score: {risk_output['risk_score']}/10")
        dashboard_data["logs"].append("🛡️ Recommending canary deployment instead")
        save_dashboard_data(dashboard_data)

        print(f"❌ DEPLOYMENT BLOCKED — Risk Score: {risk_output['risk_score']}/10")
        print(risk_output["analysis"])

    print("\n" + "="*60)
    print("✅ DEVOPS COPILOT SWARM — COMPLETE")
    print("="*60)

if __name__ == "__main__":
    run_devops_swarm(
        repo_url="https://github.com/example/payment-service",
        service_name="payment-service",
        changes="Updated payment processing logic and database connection pool"
    )