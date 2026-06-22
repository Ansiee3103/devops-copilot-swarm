from backend.core.logger import get_logger
from utils.groq_client import ask_llm

logger = get_logger("cost_service")

RESOURCE_COSTS = {
    "gcp": {
        "cpu_per_core_per_hour":    0.048,
        "memory_per_gb_per_hour":   0.006,
        "storage_per_gb_per_month": 0.02
    },
    "aws": {
        "cpu_per_core_per_hour":    0.0464,
        "memory_per_gb_per_hour":   0.00587,
        "storage_per_gb_per_month": 0.023
    },
    "azure": {
        "cpu_per_core_per_hour":    0.044,
        "memory_per_gb_per_hour":   0.0055,
        "storage_per_gb_per_month": 0.018
    }
}

class CostIntelligenceService:

    def estimate_deployment_cost(
        self,
        service_name: str,
        replicas:     int     = 2,
        cpu_cores:    float   = 0.25,
        memory_gb:    float   = 0.5,
        cloud:        str     = "gcp"
    ) -> dict:
        """Estimate monthly cost of a deployment"""
        costs = RESOURCE_COSTS.get(cloud, RESOURCE_COSTS["gcp"])

        hourly  = (
            cpu_cores * costs["cpu_per_core_per_hour"] +
            memory_gb * costs["memory_per_gb_per_hour"]
        ) * replicas

        monthly = round(hourly * 24 * 30, 2)
        yearly  = round(monthly * 12, 2)

        return {
            "service_name": service_name,
            "cloud":        cloud,
            "replicas":     replicas,
            "hourly_cost":  round(hourly, 4),
            "monthly_cost": monthly,
            "yearly_cost":  yearly,
            "currency":     "USD",
            "breakdown": {
                "cpu_monthly":    round(cpu_cores * costs["cpu_per_core_per_hour"] * 24 * 30 * replicas, 2),
                "memory_monthly": round(memory_gb * costs["memory_per_gb_per_hour"] * 24 * 30 * replicas, 2)
            }
        }

    def get_cost_optimization(
        self,
        deployments: list,
        cloud: str = "gcp"
    ) -> dict:
        """AI-powered cost optimization recommendations"""

        if not deployments:
            return {"message": "No deployment data available"}

        total_cost = sum(
            self.estimate_deployment_cost(
                d.get("service_name", ""),
                cloud=cloud
            )["monthly_cost"]
            for d in deployments[:10]
        )

        prompt = f"""
        You are a cloud cost optimization expert.
        Current monthly infrastructure cost: ${total_cost:.2f}

        Services deployed: {[d.get('service_name') for d in deployments[:10]]}

        Provide 3 specific cost optimization recommendations:
        1. Which services can share resources
        2. Optimal replica counts based on usage
        3. Estimated savings possible

        Be specific with dollar amounts and percentages.
        """

        recommendations = ask_llm(prompt)

        return {
            "total_monthly_cost":  round(total_cost, 2),
            "total_yearly_cost":   round(total_cost * 12, 2),
            "recommendations":     recommendations,
            "potential_savings":   round(total_cost * 0.25, 2)
        }

cost_service = CostIntelligenceService()