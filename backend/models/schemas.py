from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Any
from datetime import datetime

# ── Standard Response ─────────────────────────────────────

class APIResponse(BaseModel):
    success:    bool
    message:    str
    data:       Optional[Any]  = None
    request_id: Optional[str]  = None

def success_response(message: str, data: Any = None) -> dict:
    return {"success": True, "message": message, "data": data}

def error_response(message: str, data: Any = None) -> dict:
    return {"success": False, "message": message, "data": data}

# ── Auth Schemas ──────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username:  str = Field(..., min_length=3, max_length=50)
    email:     str
    full_name: str = Field(..., min_length=2)
    password:  str = Field(..., min_length=6)

class TokenResponse(BaseModel):
    access_token: str
    token_type:   str  = "bearer"
    username:     str
    full_name:    str
    role:         str
    is_admin:     bool

class UserResponse(BaseModel):
    id:         int
    username:   str
    email:      str
    full_name:  str
    role:       str
    is_admin:   bool
    created_at: str

# ── Deployment Schemas ────────────────────────────────────

class DeployRequest(BaseModel):
    repo_url:     str = Field(..., description="GitHub repository URL")
    service_name: str = Field(..., description="Microservice name to deploy")
    changes:      str = Field(..., min_length=3, max_length=500)

    class Config:
        json_schema_extra = {
            "example": {
                "repo_url":     "https://github.com/GoogleCloudPlatform/microservices-demo",
                "service_name": "emailservice",
                "changes":      "Updated email template for order confirmation"
            }
        }

class DeploymentResponse(BaseModel):
    id:                  int
    service_name:        str
    repo_url:            str
    language:            Optional[str]
    status:              str
    risk_score:          float
    is_safe:             bool
    is_critical:         bool
    affected_services:   List[str]
    downstream_services: List[str]
    generated_files:     List[str]
    risk_analysis:       Optional[str]
    healing_report:      Optional[str]
    logs:                List[str]
    created_at:          str
    updated_at:          str

class DeploymentSummary(BaseModel):
    id:           int
    service_name: str
    language:     Optional[str]
    status:       str
    risk_score:   float
    is_critical:  bool
    created_at:   str

class StatsResponse(BaseModel):
    total_deployments: int
    successful:        int
    blocked:           int
    failed:            int
    avg_risk_score:    float
    success_rate:      float