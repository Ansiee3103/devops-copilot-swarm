import pytest
from unittest.mock import patch

def test_blast_radius_critical_service():
    from agents.blast_radius import blast_radius_agent

    with patch("agents.blast_radius.ask_llm") as mock_llm:
        mock_llm.return_value = """
        1. Risk Score: 8/10
        2. Affected Services: frontend, checkoutservice
        3. Risk Reasons: Critical payment service
        4. Recommendation: BLOCK DEPLOYMENT
        5. Safer Alternative: Use canary deployment
        """
        result = blast_radius_agent("paymentservice", "Updated logic")
        assert result["risk_score"]  >= 6
        assert result["is_safe"]     == False
        assert result["is_critical"] == True

def test_blast_radius_safe_service():
    from agents.blast_radius import blast_radius_agent

    with patch("agents.blast_radius.ask_llm") as mock_llm:
        mock_llm.return_value = """
        1. Risk Score: 2/10
        2. Affected Services: None
        3. Risk Reasons: Low risk change
        4. Recommendation: SAFE TO DEPLOY
        5. Safer Alternative: None needed
        """
        result = blast_radius_agent("emailservice", "Minor template update")
        assert result["risk_score"] <= 5
        assert result["is_safe"]    == True

def test_dependency_map_exists():
    from agents.blast_radius import DEPENDENCY_MAP, REVERSE_DEPENDENCY_MAP
    assert "frontend"        in DEPENDENCY_MAP
    assert "checkoutservice" in DEPENDENCY_MAP
    assert "paymentservice"  in REVERSE_DEPENDENCY_MAP

def test_validate_valid_service():
    from backend.validators import validate_deploy_request
    validate_deploy_request(
        service_name = "emailservice",
        repo_url     = "https://github.com/GoogleCloudPlatform/microservices-demo",
        changes      = "Minor update"
    )

def test_validate_invalid_service():
    from backend.validators import validate_deploy_request
    with pytest.raises(ValueError):
        validate_deploy_request(
            service_name = "invalid-service",
            repo_url     = "https://github.com/GoogleCloudPlatform/microservices-demo",
            changes      = "Minor update"
        )

def test_validate_empty_changes():
    from backend.validators import validate_deploy_request
    with pytest.raises(ValueError):
        validate_deploy_request(
            service_name = "emailservice",
            repo_url     = "https://github.com/GoogleCloudPlatform/microservices-demo",
            changes      = ""
        )

def test_validate_username_valid():
    from backend.validators import validate_username
    validate_username("admin_user")

def test_validate_username_too_short():
    from backend.validators import validate_username
    with pytest.raises(ValueError):
        validate_username("ab")

def test_validate_password_valid():
    from backend.validators import validate_password
    validate_password("securepassword")

def test_validate_password_too_short():
    from backend.validators import validate_password
    with pytest.raises(ValueError):
        validate_password("abc")