import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from backend.core.config     import settings
from backend.core.logger     import get_logger
from backend.core.exceptions import (
    AppException, app_exception_handler,
    validation_exception_handler,
    http_exception_handler,
    generic_exception_handler
)
from backend.core.middleware import RequestMiddleware, SecurityHeadersMiddleware
from backend.database        import create_tables

from backend.api.v1.deployments import router as deploy_router
from backend.api.v1.auth        import router as auth_router
from backend.api.v1.cluster     import router as cluster_router
from backend.api.v1.alerts      import router as alerts_router
from backend.api.v1.system      import router as system_router
from backend.api.v1.saas  import router as saas_router
from backend.api.v1.admin import router as admin_router
from backend.api.v1.aiops import router as aiops_router

logger  = get_logger("main")
limiter = Limiter(key_func=get_remote_address)

# ── Lifespan ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} starting...")

    # Create DB tables
    create_tables()

    # Create directories
    for d in ["outputs", "logs", "database"]:
        os.makedirs(d, exist_ok=True)

    # Create default admin
    from backend.database import SessionLocal
    from backend.repositories.user_repo import UserRepository
    db   = SessionLocal()
    repo = UserRepository(db)
    repo.create_admin_if_not_exists()
    db.close()

    logger.info("✅ Startup complete")
    yield
    logger.info("👋 Shutting down...")

# ── App Factory ───────────────────────────────────────────
app = FastAPI(
    title        = settings.APP_NAME,
    description  = "Risk-Aware Deployment & Self-Healing Control Plane",
    version      = settings.APP_VERSION,
    docs_url     = "/docs",
    redoc_url    = "/redoc",
    lifespan     = lifespan,
    swagger_ui_parameters = {"persistAuthorization": True}
)

# ── Middleware ─────────────────────────────────────────────
app.add_middleware(RequestMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins     = settings.ALLOWED_ORIGINS,
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ── Exception Handlers ────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded,       _rate_limit_exceeded_handler)
app.add_exception_handler(AppException,            app_exception_handler)
app.add_exception_handler(RequestValidationError,  validation_exception_handler)
app.add_exception_handler(Exception,               generic_exception_handler)

# ── Routers ───────────────────────────────────────────────
app.include_router(system_router)
app.include_router(auth_router)
app.include_router(deploy_router)
app.include_router(cluster_router)
app.include_router(alerts_router)
app.include_router(saas_router)
app.include_router(admin_router)
app.include_router(aiops_router)

# ── Metrics ───────────────────────────────────────────────
if settings.METRICS_ENABLED:
    try:
        from prometheus_fastapi_instrumentator import Instrumentator
        Instrumentator().instrument(app).expose(app, endpoint="/metrics")
        logger.info("✅ Prometheus metrics enabled")
    except ImportError:
        logger.warning("⚠️ prometheus-fastapi-instrumentator not installed")

# ── Dashboard ─────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASHBOARD_DIR = os.path.join(BASE_DIR, "dashboard")

if os.path.exists(DASHBOARD_DIR):
    app.mount("/dashboard", StaticFiles(directory=DASHBOARD_DIR), name="dashboard")
    logger.info(f"✅ Dashboard: {DASHBOARD_DIR}")