import uuid
import time
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from backend.core.logger import get_logger

logger = get_logger("middleware")

SKIP_LOGGING = ["/health", "/metrics", "/favicon.ico"]

class RequestMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        start_time = time.time()

        try:
            response  = await call_next(request)
            duration  = round((time.time() - start_time) * 1000, 2)

            response.headers["X-Request-ID"]    = request_id
            response.headers["X-Response-Time"] = f"{duration}ms"
            response.headers["X-API-Version"]   = "v1"

            if request.url.path not in SKIP_LOGGING:
                logger.info(
                    f"{request.method} {request.url.path} "
                    f"→ {response.status_code} ({duration}ms) "
                    f"[{request_id}]"
                )
            return response

        except Exception as e:
            duration = round((time.time() - start_time) * 1000, 2)
            logger.error(f"Request failed [{request_id}]: {e}")
            return JSONResponse(
                status_code = 500,
                content = {
                    "success":    False,
                    "message":    "Internal server error",
                    "request_id": request_id
                }
            )

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"]    = "nosniff"
        response.headers["X-Frame-Options"]           = "DENY"
        response.headers["X-XSS-Protection"]          = "1; mode=block"
        response.headers["Referrer-Policy"]           = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"]        = "geolocation=(), microphone=()"
        return response