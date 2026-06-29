import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
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
from backend.api.v1.saas       import router as saas_router
from backend.api.v1.admin      import router as admin_router
from backend.api.v1.aiops      import router as aiops_router
from backend.api.v1.dora       import router as dora_router
from backend.api.v1.incidents  import router as incidents_router
from backend.api.v1.webhooks   import router as webhooks_router
from backend.api.v1.rollbacks  import router as rollbacks_router
from backend.api.v1.audit      import router as audit_router
from backend.api.v1.websocket  import router as ws_router
from backend.api.v1.scheduler  import router as scheduler_router
from backend.api.v1.slo        import router as slo_router

logger  = get_logger("main")
limiter = Limiter(key_func=get_remote_address)

# ── Lifespan ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} starting...")

    # Create DB tables (including new Incident table)
    create_tables()

    # Create directories
    for d in ["outputs", "logs", "database", "outputs/manifests"]:
        os.makedirs(d, exist_ok=True)

    # Create default admin
    from backend.database import SessionLocal
    from backend.repositories.user_repo import UserRepository
    db   = SessionLocal()
    repo = UserRepository(db)
    repo.create_admin_if_not_exists()
    db.close()

    # Start event bus
    try:
        from backend.services.event_bus import event_bus
        event_bus.start_redis_listener()
        logger.info("✅ Event bus started")
    except Exception as e:
        logger.warning(f"⚠️ Event bus startup skipped: {e}")

    # Start Scheduler Service
    try:
        from backend.services.scheduler_service import scheduler_service
        scheduler_service.start()
        logger.info("✅ Scheduler service started")
    except Exception as e:
        logger.warning(f"⚠️ Scheduler service startup failed: {e}")

    logger.info("✅ Startup complete")
    yield

    # Shutdown Scheduler Service
    try:
        from backend.services.scheduler_service import scheduler_service
        scheduler_service.stop()
    except Exception:
        pass

    # Shutdown event bus
    try:
        from backend.services.event_bus import event_bus
        event_bus.stop()
    except Exception:
        pass
    logger.info("👋 Shutting down...")

# ── App Factory ───────────────────────────────────────────
app = FastAPI(
    title        = settings.APP_NAME,
    description  = "Risk-Aware Deployment & Self-Healing Control Plane",
    version      = settings.APP_VERSION,
    docs_url     = None,       # Disable default Swagger
    redoc_url    = None,       # Disable ReDoc
    lifespan     = lifespan,
)

from fastapi.responses import HTMLResponse

@app.get("/docs", include_in_schema=False)
async def scalar_html():
    agent_config = {"disabled": False}
    if settings.SCALAR_AGENT_KEY:
        agent_config["key"] = settings.SCALAR_AGENT_KEY

    import json
    config = {
        "url": "/openapi.json",
        "theme": "deepSpace",
        "layout": "modern",
        "darkMode": True,
        "showSidebar": True,
        "agent": agent_config
    }
    config_json = json.dumps(config)

    return HTMLResponse(
        f"""
        <!doctype html>
        <html>
        <head>
          <meta charset="utf-8">
          <title>DevOps Copilot Swarm - API Reference</title>
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <style>
            body {{
              margin: 0;
              background-color: #0d1117;
            }}
            /* Custom Scrollbar */
            ::-webkit-scrollbar {{
              width: 8px;
              height: 8px;
            }}
            ::-webkit-scrollbar-track {{
              background: #0d1117;
            }}
            ::-webkit-scrollbar-thumb {{
              background: #30363d;
              border-radius: 4px;
            }}
            ::-webkit-scrollbar-thumb:hover {{
              background: #8b949e;
            }}
            /* Custom styles to match DevOps Swarm UI */
            :root {{
              --scalar-color-1: #e6edf3 !important;
              --scalar-color-2: #8b949e !important;
              --scalar-color-accent: #58a6ff !important;
              --scalar-background-1: #0d1117 !important;
              --scalar-background-2: #161b22 !important;
              --scalar-border-color: #30363d !important;
              --scalar-font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
              --scalar-font-code: "Courier New", Courier, monospace !important;
              --scalar-radius: 8px !important;
              --scalar-radius-lg: 12px !important;
            }}
          </style>
        </head>
        <body>
          <div id="api-reference"></div>
          <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
          <script>
            Scalar.createApiReference('#api-reference', {config_json})
          </script>
        </body>
        </html>
        """
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
app.include_router(dora_router)
app.include_router(incidents_router)
app.include_router(webhooks_router)
app.include_router(rollbacks_router)
app.include_router(audit_router)
app.include_router(ws_router)
app.include_router(scheduler_router)
app.include_router(slo_router)

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