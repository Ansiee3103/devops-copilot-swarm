from enum import Enum
from backend.core.logger import get_logger

logger = get_logger("cloud_providers")

class CloudProvider(str, Enum):
    GCP   = "gcp"
    AWS   = "aws"
    AZURE = "azure"
    LOCAL = "local"

class MultiCloudManager:
    """Unified interface for GCP, AWS, Azure"""

    def deploy(self, provider: CloudProvider, service_name: str,
               manifest_path: str) -> dict:
        deployers = {
            CloudProvider.GCP:   self._deploy_gcp,
            CloudProvider.AWS:   self._deploy_aws,
            CloudProvider.AZURE: self._deploy_azure,
            CloudProvider.LOCAL: self._deploy_local,
        }
        return deployers[provider](service_name, manifest_path)

    def _deploy_local(self, service_name: str, manifest: str) -> dict:
        import subprocess
        result = subprocess.run(
            ["kubectl", "apply", "-f", manifest],
            capture_output=True, text=True
        )
        return {
            "provider": "local",
            "success":  result.returncode == 0,
            "output":   result.stdout,
            "error":    result.stderr
        }

    def _deploy_gcp(self, service_name: str, manifest: str) -> dict:
        import os
        project = os.getenv("GCP_PROJECT_ID")
        cluster = os.getenv("GKE_CLUSTER_NAME")
        zone    = os.getenv("GKE_ZONE")

        if not all([project, cluster, zone]):
            return {
                "provider": "gcp",
                "success":  False,
                "error":    "GCP credentials not configured"
            }

        import subprocess
        # Get credentials
        subprocess.run([
            "gcloud", "container", "clusters", "get-credentials",
            cluster, "--zone", zone, "--project", project
        ], capture_output=True)

        # Apply manifest
        result = subprocess.run(
            ["kubectl", "apply", "-f", manifest],
            capture_output=True, text=True
        )
        return {
            "provider": "gcp",
            "success":  result.returncode == 0,
            "output":   result.stdout
        }

    def _deploy_aws(self, service_name: str, manifest: str) -> dict:
        import os, subprocess
        cluster = os.getenv("EKS_CLUSTER_NAME")
        region  = os.getenv("AWS_REGION")

        if not all([cluster, region]):
            return {
                "provider": "aws",
                "success":  False,
                "error":    "AWS credentials not configured"
            }

        # Update kubeconfig for EKS
        subprocess.run([
            "aws", "eks", "update-kubeconfig",
            "--name", cluster,
            "--region", region
        ], capture_output=True)

        result = subprocess.run(
            ["kubectl", "apply", "-f", manifest],
            capture_output=True, text=True
        )
        return {
            "provider": "aws",
            "success":  result.returncode == 0,
            "output":   result.stdout
        }

    def _deploy_azure(self, service_name: str, manifest: str) -> dict:
        import os, subprocess
        resource_group = os.getenv("AZURE_RESOURCE_GROUP")
        cluster        = os.getenv("AKS_CLUSTER_NAME")

        if not all([resource_group, cluster]):
            return {
                "provider": "azure",
                "success":  False,
                "error":    "Azure credentials not configured"
            }

        subprocess.run([
            "az", "aks", "get-credentials",
            "--resource-group", resource_group,
            "--name", cluster
        ], capture_output=True)

        result = subprocess.run(
            ["kubectl", "apply", "-f", manifest],
            capture_output=True, text=True
        )
        return {
            "provider": "azure",
            "success":  result.returncode == 0,
            "output":   result.stdout
        }

    def get_cost_estimate(self, provider: CloudProvider,
                          service_name: str, replicas: int) -> dict:
        """Estimate cloud cost for deployment"""
        # Cost per replica per month (approximate)
        costs = {
            CloudProvider.GCP:   {"cpu": 0.048, "memory": 0.006},
            CloudProvider.AWS:   {"cpu": 0.0464, "memory": 0.00587},
            CloudProvider.AZURE: {"cpu": 0.044,  "memory": 0.0055},
            CloudProvider.LOCAL: {"cpu": 0,      "memory": 0}
        }

        cost    = costs.get(provider, costs[CloudProvider.LOCAL])
        monthly = round((cost["cpu"] * 0.25 + cost["memory"] * 512) * replicas, 2)

        return {
            "provider":        provider,
            "replicas":        replicas,
            "monthly_cost_usd": monthly,
            "yearly_cost_usd":  monthly * 12,
            "currency":        "USD"
        }

cloud_manager = MultiCloudManager()