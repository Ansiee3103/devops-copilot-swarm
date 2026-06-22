from utils.groq_client import ask_llm

# Real Online Boutique dependency map
DEPENDENCY_MAP = {
    "frontend": [
        "cartservice", "productcatalogservice", "currencyservice",
        "paymentservice", "shippingservice", "checkoutservice",
        "recommendationservice", "adservice"
    ],
    "checkoutservice": [
        "cartservice", "productcatalogservice", "currencyservice",
        "paymentservice", "shippingservice", "emailservice"
    ],
    "cartservice":            ["redis-cart"],
    "recommendationservice":  ["productcatalogservice"],
    "productcatalogservice":  [],
    "paymentservice":         [],
    "shippingservice":        [],
    "currencyservice":        [],
    "emailservice":           [],
    "adservice":              [],
    "loadgenerator":          ["frontend"]
}

REVERSE_DEPENDENCY_MAP = {
    "frontend":               ["loadgenerator"],
    "cartservice":            ["frontend", "checkoutservice"],
    "productcatalogservice":  ["frontend", "checkoutservice", "recommendationservice"],
    "currencyservice":        ["frontend", "checkoutservice"],
    "paymentservice":         ["checkoutservice"],
    "shippingservice":        ["frontend", "checkoutservice"],
    "emailservice":           ["checkoutservice"],
    "checkoutservice":        ["frontend"],
    "recommendationservice":  ["frontend"],
    "adservice":              ["frontend"],
    "redis-cart":             ["cartservice"]
}

CRITICAL_SERVICES = [
    "paymentservice", "checkoutservice",
    "cartservice", "frontend",
    "productcatalogservice", "currencyservice"
]

def blast_radius_agent(service_name: str, changes_description: str) -> dict:
    print("\n🔍 Blast Radius Agent — Analyzing deployment risk...")

    downstream  = DEPENDENCY_MAP.get(service_name, [])
    upstream    = REVERSE_DEPENDENCY_MAP.get(service_name, [])
    is_critical = service_name in CRITICAL_SERVICES

    prompt = f"""
    You are a microservices risk analyst for Google's Online Boutique app.

    Service being deployed : {service_name}
    Changes made           : {changes_description}
    Services this calls    : {', '.join(downstream) if downstream else 'None'}
    Services calling this  : {', '.join(upstream) if upstream else 'None'}
    Is critical service    : {is_critical}

    Service roles in Online Boutique:
    - frontend            : Main web UI — ALL users hit this
    - checkoutservice     : Orchestrates payment, shipping, cart, email
    - paymentservice      : Handles ALL financial transactions
    - cartservice         : Manages shopping carts via Redis
    - productcatalogservice: Serves product data to multiple services
    - currencyservice     : Highest QPS — currency conversions
    - emailservice        : Sends order confirmations
    - shippingservice     : Calculates shipping costs
    - recommendationservice: Product recommendations
    - adservice           : Serves advertisements

    Respond with EXACTLY this format:
    1. Risk Score: X/10
    2. Affected Services: [comma separated list]
    3. Risk Reasons: [specific reasons]
    4. Recommendation: SAFE TO DEPLOY or BLOCK DEPLOYMENT
    5. Safer Alternative: [specific suggestion]
    """

    analysis = ask_llm(prompt)

    # Extract risk score from response
    risk_score = 6 if is_critical else 4
    for line in analysis.split('\n'):
        if 'Risk Score:' in line:
            for word in line.split():
                if '/10' in word:
                    try:
                        risk_score = int(word.replace('/10', '').strip())
                    except:
                        pass

    if is_critical and risk_score < 6:
        risk_score = 6

    is_safe = risk_score < 6

    print(f"✅ Blast Radius — Risk Score: {risk_score}/10")
    print(f"{'✅ SAFE TO DEPLOY' if is_safe else '❌ DEPLOYMENT BLOCKED'}")
    print(analysis)

    return {
        "risk_score":          risk_score,
        "is_safe":             is_safe,
        "affected_services":   upstream,
        "downstream_services": downstream,
        "is_critical":         is_critical,
        "analysis":            analysis
    }
def recommend_deployment_strategy(
    service_name: str,
    risk_score:   float,
    is_critical:  bool
) -> dict:
    """Recommend deployment strategy based on risk"""

    if risk_score <= 3:
        return {
            "strategy":    "rolling",
            "description": "Standard rolling deployment",
            "config": {
                "maxUnavailable": 1,
                "maxSurge":       1
            }
        }
    elif risk_score <= 6:
        return {
            "strategy":    "canary",
            "description": "Canary deployment — 10% traffic first",
            "config": {
                "initial_weight":  10,
                "increment":       20,
                "interval_minutes": 10,
                "success_threshold": 99.0
            }
        }
    elif risk_score <= 8:
        return {
            "strategy":    "blue_green",
            "description": "Blue-green deployment — full standby swap",
            "config": {
                "health_check_interval": 30,
                "rollback_on_failure":   True
            }
        }
    else:
        return {
            "strategy":    "block",
            "description": "Deployment blocked — risk too high",
            "config": {
                "reason":      "Risk score exceeds threshold",
                "suggestions": [
                    "Break change into smaller deployments",
                    "Add more test coverage",
                    "Deploy during off-peak hours",
                    "Get additional peer review"
                ]
            }
        }