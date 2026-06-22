import pytest
import numpy as np
from unittest.mock import patch, MagicMock

def test_risk_model_heuristic_critical_service():
    from backend.ml.risk_model import risk_model
    result = risk_model.predict("paymentservice", "Updated payment logic")
    assert result["risk_score"] >= 6
    assert result["is_safe"] == False
    assert result["source"] in ["ml_model", "heuristic"]

def test_risk_model_heuristic_safe_service():
    from backend.ml.risk_model import risk_model
    result = risk_model.predict("emailservice", "Minor template update")
    assert result["risk_score"] <= 7
    assert "confidence" in result
    assert "features" in result

def test_risk_model_friday_penalty():
    from backend.ml.risk_model import extract_features
    # Friday = weekday 4
    features_friday  = extract_features("emailservice", "update", day_of_week=4)
    features_monday  = extract_features("emailservice", "update", day_of_week=0)
    # Friday should have is_friday=1
    assert features_friday[0][7] == 1
    assert features_monday[0][7] == 0

def test_risk_model_training_insufficient_data():
    from backend.ml.risk_model import risk_model
    result = risk_model.train([{"service_name": "test", "status": "healed"}])
    assert result["success"] == False
    assert "10" in result["message"]

def test_risk_model_training_synthetic():
    from backend.ml.risk_model import risk_model

    # Generate synthetic training data
    synthetic = []
    for i in range(20):
        synthetic.append({
            "service_name":  "paymentservice" if i % 2 == 0 else "emailservice",
            "changes":       "payment update" if i % 2 == 0 else "template fix",
            "status":        "blocked" if i % 2 == 0 else "healed",
            "risk_score":    8.0 if i % 2 == 0 else 2.0,
            "prev_failures": 0
        })

    result = risk_model.train(synthetic)
    assert result["success"] == True
    assert result["samples"] == 20
    assert result["accuracy"] >= 0

def test_cost_estimate_gcp():
    from backend.services.cost_service import cost_service
    result = cost_service.estimate_deployment_cost(
        "emailservice", replicas=2, cloud="gcp"
    )
    assert result["monthly_cost"] > 0
    assert result["yearly_cost"]  > result["monthly_cost"]
    assert result["currency"]     == "USD"
    assert "breakdown" in result

def test_cost_estimate_aws_vs_gcp():
    from backend.services.cost_service import cost_service
    gcp = cost_service.estimate_deployment_cost("svc", replicas=2, cloud="gcp")
    aws = cost_service.estimate_deployment_cost("svc", replicas=2, cloud="aws")
    # Both should return positive costs
    assert gcp["monthly_cost"] > 0
    assert aws["monthly_cost"] > 0

def test_compliance_dockerfile_check():
    from backend.services.compliance_service import compliance_engine
    good_dockerfile = """
FROM golang:1.21 AS builder
WORKDIR /app
COPY . .
RUN go build -o app .

FROM gcr.io/distroless/static-debian12
RUN adduser -D appuser
USER appuser
COPY --from=builder /app/app .
EXPOSE 8080
HEALTHCHECK CMD curl -f http://localhost:8080/health
CMD ["./app"]
"""
    with patch("backend.services.compliance_service.ask_llm") as mock:
        mock.return_value = '{"passed": ["Non-root user", "Health check"], "failed": [], "warnings": [], "compliance_score": 90, "critical_issues": [], "recommendations": []}'
        result = compliance_engine.check_dockerfile(good_dockerfile, "SOC2")
        assert "compliance_score" in result

def test_plugin_register_and_trigger():
    from backend.plugins.plugin_manager import PluginManager, Plugin

    manager = PluginManager()

    class TestPlugin(Plugin):
        name    = "test_plugin"
        version = "1.0.0"
        triggered = False

        def on_deploy_start(self, context):
            TestPlugin.triggered = True
            return context

    plugin = TestPlugin()
    manager.register(plugin)
    assert "test_plugin" in manager.plugins

    context = manager.trigger("deploy_start", {"service": "test"})
    assert TestPlugin.triggered == True

    manager.unregister("test_plugin")
    assert "test_plugin" not in manager.plugins

def test_plugin_list():
    from backend.plugins.plugin_manager import plugin_manager
    plugins = plugin_manager.list_plugins()
    assert isinstance(plugins, list)
    assert len(plugins) >= 3  # 3 built-in plugins