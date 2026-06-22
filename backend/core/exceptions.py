from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from backend.core.logger import get_logger

logger = get_logger("exceptions")

class AppException(Exception):
    def __init__(self, message: str, code: int = 500, details: dict = None):
        self.message = message
        self.code    = code
        self.details = details or {}
        super().__init__(message)

class AgentException(AppException):
    pass

class DeploymentException(AppException):
    pass

class KubernetesException(AppException):
    pass

class ValidationException(AppException):
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, code=400, details=details)

class AuthException(AppException):
    def __init__(self, message: str):
        super().__init__(message, code=401)

class PermissionException(AppException):
    def __init__(self, message: str):
        super().__init__(message, code=403)

class NotFoundException(AppException):
    def __init__(self, resource: str, id: int):
        super().__init__(f"{resource} #{id} not found", code=404)

# ── Handlers ──────────────────────────────────────────────

def error_response(code: int, message: str, details: dict = None, request_id: str = None):
    return JSONResponse(
        status_code = code,
        content = {
            "success":    False,
            "message":    message,
            "details":    details or {},
            "request_id": request_id
        }
    )

async def app_exception_handler(request: Request, exc: AppException):
    logger.error(f"{exc.__class__.__name__}: {exc.message}")
    return error_response(
        exc.code,
        exc.message,
        exc.details,
        getattr(request.state, "request_id", None)
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = {}
    for err in exc.errors():
        field = ".".join(str(x) for x in err["loc"])
        errors[field] = err["msg"]
    logger.warning(f"Validation error: {errors}")
    return error_response(422, "Validation failed", errors)

async def http_exception_handler(request: Request, exc: HTTPException):
    return error_response(exc.status_code, exc.detail)

async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}")
    return error_response(500, "Internal server error")