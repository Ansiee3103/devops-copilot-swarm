import pytest
from datetime import datetime, timedelta, timezone
from backend.database import SessionLocal
from backend.services.secrets_scanner import secrets_scanner
from backend.services.slo_service import SLOService
from backend.services.scheduler_service import scheduler_service, ScheduledDeployment
from backend.core.rbac import ROLES
from backend.core.security import ROLE_PERMISSIONS

IST = timezone(timedelta(hours=5, minutes=30))

def test_secrets_scanner():
    # Test valid text (no secrets)
    assert len(secrets_scanner.scan_text("This is a normal changes description without keys.")) == 0

    # Test AWS Access Key
    findings = secrets_scanner.scan_text("My key is AKIA1234567890123456.")
    assert len(findings) == 1
    assert findings[0]["secret_type"] == "AWS Access Key ID"
    assert "REDACTED" in findings[0]["snippet"]

    # Test Private Key
    findings = secrets_scanner.scan_text("-----BEGIN PRIVATE KEY-----\nMIIEowIBAAKCAQEA...\n-----END PRIVATE KEY-----")
    assert len(findings) == 1
    assert findings[0]["secret_type"] == "Private Key"

    # Test Slack Webhook
    findings = secrets_scanner.scan_text("Send alerts to https://hooks.slack.com/services/T12345/B67890/abcdef123456")
    assert len(findings) == 1
    assert findings[0]["secret_type"] == "Slack Webhook"


def test_slo_guardrail():
    db = SessionLocal()
    try:
        slo_service = SLOService(db)
        
        # Test a clean service
        status = slo_service.get_service_slo_status("emailservice")
        assert status["exhausted"] is False
        assert status["consumed_downtime_minutes"] == 0.0
        
        guardrail = slo_service.check_guardrail("emailservice")
        assert guardrail["safe"] is True
        
    finally:
        db.close()


def test_scheduler_service():
    db = SessionLocal()
    try:
        # Create a schedule
        target_time = datetime.now(IST) + timedelta(hours=1)
        job = scheduler_service.create_schedule(
            db=db,
            service_name="emailservice",
            repo_url="https://github.com/GoogleCloudPlatform/microservices-demo.git",
            changes="Scheduled deployment test",
            scheduled_at=target_time,
            user_id=1
        )
        
        assert job.id is not None
        assert job.service_name == "emailservice"
        assert job.status == "pending"
        
        # Retrieve schedules
        jobs = scheduler_service.get_all(db)
        assert len(jobs) >= 1
        assert any(j.id == job.id for j in jobs)
        
        # Cancel schedule
        cancelled = scheduler_service.cancel_schedule(db, job.id)
        assert cancelled is True
        
        # Verify it is cancelled
        db.refresh(job)
        assert job.status == "cancelled"
        
    finally:
        db.close()


def test_unified_rbac():
    # Verify both permissions dictionaries match
    for role, data in ROLES.items():
        perms = data["permissions"]
        sec_perms = ROLE_PERMISSIONS[role]
        assert set(perms) == sec_perms
