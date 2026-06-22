import os
import secrets
from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # ── App ───────────────────────────────────────────────
    APP_NAME:        str  = "DevOps Copilot Swarm"
    APP_VERSION:     str  = "2.0.0"
    APP_ENV:         str  = "production"
    DEBUG:           bool = False

    # ── API ───────────────────────────────────────────────
    API_V1_PREFIX:   str  = "/api/v1"
    ALLOWED_ORIGINS: list = ["*"]

    # ── Database ──────────────────────────────────────────
    DATABASE_URL:    str  = "sqlite:///database/devops.db"

    # ── Redis ─────────────────────────────────────────────
    REDIS_HOST:      str  = "localhost"
    REDIS_PORT:      int  = 6379

    # ── Security ──────────────────────────────────────────
    SECRET_KEY:               str = secrets.token_hex(32)
    TOKEN_EXPIRE_MINUTES:     int = 480
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── LLM Providers ─────────────────────────────────────
    GROQ_API_KEY:      str = ""
    MISTRAL_API_KEY:   str = ""
    COHERE_API_KEY:    str = ""
    OPENCODE_API_KEY:  str = ""
    GROQ_MODEL:        str = "llama-3.3-70b-versatile"
    OPENCODE_MODEL:    str = "deepseek-v4-flash-free"
    LLM_MAX_TOKENS:    int = 1500
    LLM_MAX_RETRIES:   int = 3
    LLM_TIMEOUT:       int = 60

    # ── Email ─────────────────────────────────────────────
    EMAIL_SENDER:    str = ""
    EMAIL_PASSWORD:  str = ""
    EMAIL_RECEIVER:  str = ""

    # ── Slack ─────────────────────────────────────────────
    SLACK_WEBHOOK_URL: str = ""

    # ── Kubernetes ────────────────────────────────────────
    K8S_NAMESPACE:   str = "default"
    K8S_TIMEOUT:     int = 30

    # ── Rate Limiting ─────────────────────────────────────
    RATE_LIMIT_DEPLOY:  str = "10/minute"
    RATE_LIMIT_GLOBAL:  str = "100/minute"

    # ── Monitoring ────────────────────────────────────────
    METRICS_ENABLED: bool = True

    class Config:
        env_file       = ".env"
        case_sensitive = True
        extra          = "ignore"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()