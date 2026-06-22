import pytest

# ── Fixtures ──────────────────────────────────────────────
@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from backend.main import app
    return TestClient(app)

# ── Helpers ───────────────────────────────────────────────
def get_token(client):
    """Get fresh token — creates admin if needed"""
    from backend.database import SessionLocal
    from backend.repositories.user_repo import UserRepository

    db = SessionLocal()
    repo = UserRepository(db)
    repo.create_admin_if_not_exists()
    db.close()

    res = client.post("/auth/login", data={
        "username": "admin",
        "password": "admin123"
    })
    assert res.status_code == 200, f"Login failed: {res.json()}"
    return res.json()["access_token"]

def auth_headers(client):
    return {"Authorization": f"Bearer {get_token(client)}"}

# ── System Tests ──────────────────────────────────────────
def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

def test_docs_available(client):
    res = client.get("/docs")
    assert res.status_code == 200

# ── Auth Tests ────────────────────────────────────────────
def test_login_success(client):
    from backend.database import SessionLocal
    from backend.repositories.user_repo import UserRepository
    db = SessionLocal()
    repo = UserRepository(db)
    repo.create_admin_if_not_exists()
    db.close()

    res = client.post("/auth/login", data={
        "username": "admin",
        "password": "admin123"
    })
    assert res.status_code == 200
    assert "access_token" in res.json()
    assert res.json()["username"] == "admin"

def test_login_wrong_password(client):
    res = client.post("/auth/login", data={
        "username": "admin",
        "password": "wrongpassword"
    })
    assert res.status_code == 401

def test_login_wrong_username(client):
    res = client.post("/auth/login", data={
        "username": "nonexistent",
        "password": "admin123"
    })
    assert res.status_code == 401

def test_get_me(client):
    res = client.get("/auth/me", headers=auth_headers(client))
    assert res.status_code == 200
    assert res.json()["username"] == "admin"

def test_get_me_no_auth(client):
    res = client.get("/auth/me")
    assert res.status_code == 401

# ── Deployment Tests ──────────────────────────────────────
def test_get_services(client):
    res = client.get("/api/v1/services")
    assert res.status_code == 200
    assert "services" in res.json()
    assert "emailservice" in res.json()["services"]

def test_deploy_no_auth(client):
    res = client.post("/api/v1/deploy", json={
        "repo_url":     "https://github.com/GoogleCloudPlatform/microservices-demo",
        "service_name": "emailservice",
        "changes":      "test change"
    })
    assert res.status_code == 401

def test_deploy_valid(client):
    res = client.post(
        "/api/v1/deploy",
        json={
            "repo_url":     "https://github.com/GoogleCloudPlatform/microservices-demo",
            "service_name": "emailservice",
            "changes":      "Minor update"
        },
        headers=auth_headers(client)
    )
    assert res is not None
    assert res.status_code == 200

    data = res.json()
    assert data is not None
    assert "deployment_id" in data
    assert data["status"] == "started"

def test_deploy_invalid_service(client):
    res = client.post(
        "/api/v1/deploy",
        json={
            "repo_url":     "https://github.com/GoogleCloudPlatform/microservices-demo",
            "service_name": "invalid-service-xyz",
            "changes":      "Some change"
        },
        headers=auth_headers(client)
    )
    assert res.status_code == 400

def test_deploy_empty_changes(client):
    res = client.post(
        "/api/v1/deploy",
        json={
            "repo_url":     "https://github.com/GoogleCloudPlatform/microservices-demo",
            "service_name": "emailservice",
            "changes":      ""
        },
        headers=auth_headers(client)
    )
    assert res.status_code == 422

def test_get_history(client):
    res = client.get("/api/v1/history", headers=auth_headers(client))
    assert res.status_code == 200
    assert isinstance(res.json(), list)

def test_get_stats(client):
    res = client.get("/api/v1/stats", headers=auth_headers(client))
    assert res.status_code == 200
    data = res.json()
    assert "total_deployments" in data
    assert "successful"        in data
    assert "blocked"           in data
    assert "avg_risk_score"    in data

def test_get_status_not_found(client):
    res = client.get("/api/v1/status/99999", headers=auth_headers(client))
    assert res.status_code == 404

def test_cluster_health(client):
    res = client.get("/api/v1/cluster/health", headers=auth_headers(client))
    assert res.status_code == 200

def test_cluster_chat(client):
    from unittest.mock import patch
    with patch("backend.ml.cluster_chat.ask_llm") as mock_ask:
        mock_ask.return_value = "The cluster health score is 100%.\n`kubectl get pods`"
        res = client.post(
            "/api/v1/cluster/chat",
            json={"question": "What is the status of the cluster?"},
            headers=auth_headers(client)
        )
        assert res.status_code == 200
        data = res.json()
        assert data["question"] == "What is the status of the cluster?"
        assert "100%" in data["answer"]
        assert "kubectl get pods" in data["commands"]
        assert data["intent"] == "query"
        assert data["safe"] is True