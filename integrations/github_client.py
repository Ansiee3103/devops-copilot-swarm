import requests
import os
from dotenv import load_dotenv

load_dotenv()

REPO_OWNER = "GoogleCloudPlatform"
REPO_NAME  = "microservices-demo"
BASE_URL   = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"

HEADERS = {
    "Accept": "application/vnd.github.v3+json"
}

def get_all_services() -> list:
    """Get all real services from the repo"""
    url = f"{BASE_URL}/contents/src"
    response = requests.get(url, headers=HEADERS)

    if response.status_code == 200:
        contents = response.json()
        services = [
            item["name"]
            for item in contents
            if item["type"] == "dir"
        ]
        return services
    return []

def get_service_info(service_name: str) -> dict:
    """Get real info about a specific service"""
    url = f"{BASE_URL}/contents/src/{service_name}"
    response = requests.get(url, headers=HEADERS)

    files    = []
    language = "unknown"

    if response.status_code == 200:
        contents = response.json()
        files    = [item["name"] for item in contents]

        if any(f.endswith(".go")   for f in files): language = "Go"
        elif any(f.endswith(".py") for f in files): language = "Python"
        elif any(f.endswith(".js") for f in files): language = "Node.js"
        elif any(f.endswith(".cs") for f in files): language = "C#"
        elif any(f.endswith(".java") for f in files): language = "Java"

    return {
        "service_name": service_name,
        "language":     language,
        "files":        files,
        "repo_url":     f"https://github.com/{REPO_OWNER}/{REPO_NAME}/tree/main/src/{service_name}"
    }

def get_kubernetes_manifest(service_name: str) -> str:
    """Get real K8s manifest from the repo"""
    url      = f"{BASE_URL}/contents/kubernetes-manifests"
    response = requests.get(url, headers=HEADERS)

    if response.status_code == 200:
        contents = response.json()
        for item in contents:
            if service_name.lower() in item["name"].lower():
                manifest_response = requests.get(item["download_url"])
                return manifest_response.text

    return f"# No manifest found for {service_name}"

def get_recent_commits(service_name: str, limit: int = 5) -> list:
    """Get real recent commits for a service"""
    url      = f"{BASE_URL}/commits"
    params   = {"path": f"src/{service_name}", "per_page": limit}
    response = requests.get(url, headers=HEADERS, params=params)

    commits = []
    if response.status_code == 200:
        for c in response.json():
            commits.append({
                "sha":     c["sha"][:7],
                "message": c["commit"]["message"].split("\n")[0],
                "author":  c["commit"]["author"]["name"],
                "date":    c["commit"]["author"]["date"]
            })
    return commits
