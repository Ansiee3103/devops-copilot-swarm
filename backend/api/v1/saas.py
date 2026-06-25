import secrets
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.organization import Organization, Subscription
from backend.core.security import require_permission
from backend.core.logger import get_logger
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/api/v1/saas", tags=["SaaS"])
logger = get_logger("saas")
IST    = timezone(timedelta(hours=5, minutes=30))

PLANS = {
    "free": {
        "name":          "Free",
        "price_usd":     0,
        "deploy_limit":  10,
        "features": [
            "10 deployments/month",
            "3 services",
            "Email alerts",
            "Community support"
        ]
    },
    "pro": {
        "name":          "Pro",
        "price_usd":     29,
        "deploy_limit":  100,
        "features": [
            "100 deployments/month",
            "All services",
            "Email + Slack alerts",
            "Priority support",
            "ML risk model",
            "Cost intelligence"
        ]
    },
    "enterprise": {
        "name":          "Enterprise",
        "price_usd":     99,
        "deploy_limit":  -1,  # unlimited
        "features": [
            "Unlimited deployments",
            "All services",
            "All alert channels",
            "24/7 support",
            "RBAC + Multi-tenancy",
            "Compliance reports",
            "Custom integrations",
            "SLA guarantee"
        ]
    }
}

@router.get("/plans")
def get_plans():
    """Get all available pricing plans"""
    return {"plans": PLANS}

@router.post("/register")
def register_organization(
    body: dict,
    db:   Session = Depends(get_db)
):
    """Register a new organization"""
    name  = body.get("name", "").strip()
    email = body.get("email", "").strip()
    plan  = body.get("plan", "free")

    if not name or not email:
        raise HTTPException(status_code=400, detail="Name and email required")

    if plan not in PLANS:
        raise HTTPException(status_code=400, detail=f"Invalid plan: {plan}")

    # Check duplicate
    existing = db.query(Organization).filter(
        Organization.email == email
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create slug from name
    slug    = name.lower().replace(" ", "-").replace("_", "-")
    api_key = f"dcs_{secrets.token_hex(24)}"

    org = Organization(
        name         = name,
        slug         = slug,
        email        = email,
        plan         = plan,
        api_key      = api_key,
        deploy_limit = PLANS[plan]["deploy_limit"]
    )
    db.add(org)
    db.commit()
    db.refresh(org)

    logger.info(f"New org registered: {name} ({plan})")

    return {
        "message":      f"Welcome to DevOps Copilot Swarm!",
        "org_id":       org.id,
        "org_name":     org.name,
        "plan":         org.plan,
        "api_key":      org.api_key,
        "deploy_limit": org.deploy_limit,
        "features":     PLANS[plan]["features"]
    }

@router.get("/usage")
def get_usage(
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(require_permission("read"))
):
    """Get current usage for organization"""
    from backend.models.deployment import Deployment
    from sqlalchemy import func
    import calendar

    now   = datetime.now(IST)
    start = now.replace(day=1, hour=0, minute=0, second=0)

    monthly_count = db.query(func.count(Deployment.id)).filter(
        Deployment.created_at >= start
    ).scalar()

    total_count = db.query(func.count(Deployment.id)).scalar()

    return {
        "monthly_deployments": monthly_count,
        "total_deployments":   total_count,
        "month":               now.strftime("%B %Y"),
        "plan":                "pro",
        "deploy_limit":        PLANS["pro"]["deploy_limit"],
        "limit_remaining":     PLANS["pro"]["deploy_limit"] - monthly_count
    }

@router.get("/billing")
def get_billing(
    current_user: dict = Depends(require_permission("read"))
):
    """Get billing information"""
    return {
        "current_plan": "pro",
        "amount_usd":   29,
        "next_billing": "2026-07-01",
        "payment_method": "****4242",
        "invoices": [
            {"date": "2026-06-01", "amount": 29, "status": "paid"},
            {"date": "2026-05-01", "amount": 29, "status": "paid"}
        ]
    }

@router.post("/upgrade")
def upgrade_plan(
    body:         dict,
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(require_permission("admin"))
):
    """Upgrade organization plan"""
    new_plan = body.get("plan")
    if new_plan not in PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan")

    return {
        "message":  f"Upgrade to {new_plan} plan initiated",
        "plan":     new_plan,
        "features": PLANS[new_plan]["features"],
        "redirect": "https://billing.stripe.com/checkout"
    }