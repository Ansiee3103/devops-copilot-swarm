from utils.groq_client import ask_llm
from backend.core.logger import get_logger
import json

logger = get_logger("cluster_chat")

CLUSTER_CONTEXT = """
You are an expert Kubernetes SRE assistant for Google's Online Boutique app.
You have access to real cluster data. Answer questions concisely and accurately.
When suggesting kubectl commands, format them in code blocks.
"""

class ClusterChat:
    def __init__(self):
        self.history = []

    def ask(self, question: str, cluster_data: dict = None) -> dict:
        """Answer natural language questions about the cluster and auto-execute safe actions"""

        context = f"""
Current Cluster State:
{json.dumps(cluster_data, indent=2) if cluster_data else 'No cluster data available'}

Conversation History:
{self._format_history()}

User Question: {question}

Answer the question based on the cluster state above.
If suggesting actions, provide exact kubectl commands.
Be specific and concise.
"""
        answer = ask_llm(context, CLUSTER_CONTEXT)

        # Detect intent
        intent   = self._detect_intent(question)
        commands = self._extract_commands(answer)

        # Auto-execute if intent matches an actionable command
        execution_result = None
        if intent in ("restart", "rollback", "scale_up", "scale_down", "deploy"):
            service_name = None
            q_lower = question.lower()
            services = ["emailservice", "recommendationservice", "adservice", "shippingservice", "currencyservice", "paymentservice", "cartservice", "checkoutservice", "frontend", "productcatalogservice"]
            for s in services:
                if s in q_lower:
                    service_name = s
                    break
            
            if service_name:
                from integrations.k8s_client import restart_deployment, rollback_deployment, scale_deployment
                if intent == "restart":
                    execution_result = restart_deployment(service_name)
                elif intent == "rollback":
                    execution_result = rollback_deployment(service_name)
                elif intent in ("scale_up", "scale_down"):
                    replicas = 2
                    import re
                    match = re.search(r"\b\d+\b", q_lower)
                    if match:
                        replicas = int(match.group(0))
                    execution_result = scale_deployment(service_name, replicas)
                elif intent == "deploy":
                    from backend.database import SessionLocal
                    from backend.services.deployment_service import DeploymentService
                    db = SessionLocal()
                    try:
                        deploy_service = DeploymentService(db)
                        repo_url = "https://github.com/GoogleCloudPlatform/microservices-demo.git"
                        execution_result = deploy_service.create_and_start(
                            service_name = service_name,
                            repo_url     = repo_url,
                            changes      = f"[ChatOps] Deploy triggered via chat: '{question}'",
                            user_id      = 1
                        )
                    finally:
                        db.close()

        self.history.append({
            "question": question,
            "answer":   answer
        })

        # Keep last 5 exchanges
        if len(self.history) > 5:
            self.history = self.history[-5:]

        return {
            "question": question,
            "answer":   answer,
            "intent":   intent,
            "commands": commands,
            "safe":     intent not in ["delete", "scale_down", "deploy", "restart", "rollback"],
            "execution_result": execution_result
        }

    def _detect_intent(self, question: str) -> str:
        q = question.lower()
        if any(w in q for w in ["why", "what", "explain", "status", "health"]):
            return "query"
        elif any(w in q for w in ["scale", "replicas", "increase"]):
            return "scale_up"
        elif any(w in q for w in ["decrease", "reduce", "scale down"]):
            return "scale_down"
        elif any(w in q for w in ["restart", "rollout"]):
            return "restart"
        elif any(w in q for w in ["rollback", "revert"]):
            return "rollback"
        elif any(w in q for w in ["deploy", "start pipeline", "run pipeline"]):
            return "deploy"
        elif any(w in q for w in ["delete", "remove"]):
            return "delete"
        return "query"

    def _extract_commands(self, answer: str) -> list:
        """Extract kubectl commands from answer"""
        commands = []
        lines    = answer.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith("kubectl") or line.startswith("`kubectl"):
                cmd = line.strip('`').strip()
                if cmd.startswith("kubectl"):
                    commands.append(cmd)
        return commands

    def _format_history(self) -> str:
        if not self.history:
            return "No previous messages"
        return "\n".join([
            f"Q: {h['question']}\nA: {h['answer'][:200]}..."
            for h in self.history[-3:]
        ])

cluster_chat = ClusterChat()