from utils.groq_client import ask_llm
from integrations.github_client import get_service_info, get_recent_commits

def orchestrator_agent(repo_url: str, service_name: str) -> dict:
    print("\n🧠 Orchestrator Agent — Analyzing request...")

    service_info   = get_service_info(service_name)
    recent_commits = get_recent_commits(service_name)

    commits_text = "\n".join([
        f"- [{c['sha']}] {c['message']} by {c['author']}"
        for c in recent_commits
    ]) if recent_commits else "No recent commits found"

    system = """You are a senior DevOps orchestrator AI for
    Google's Online Boutique microservices e-commerce application.
    Be specific, concise, and technical."""

    prompt = f"""
    Deployment Request:
    Service     : {service_name}
    Repository  : {repo_url}
    Language    : {service_info['language']}
    Files       : {', '.join(service_info['files'][:10])}

    Recent Commits:
    {commits_text}

    Create a deployment plan with:
    1. Service Type and Purpose in Online Boutique architecture
    2. Required Resources (CPU, Memory, Replicas)
    3. Key Dependencies to verify before deployment
    4. Step-by-step Deployment Plan
    5. Specific Risks for this service
    """

    plan = ask_llm(prompt, system)

    print("✅ Orchestrator — Plan created!")
    print(plan)

    return {
        "service_name":   service_name,
        "repo_url":       repo_url,
        "language":       service_info["language"],
        "files":          service_info["files"],
        "plan":           plan,
        "recent_commits": recent_commits
    }