from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import DataGuardError
from app.core.logging import get_logger

logger = get_logger(__name__)


def error_response(status: int, code: str, message: str, details: dict[str, Any] | None = None):
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details or {}}},
    )


async def handle_dataguard_error(request: Request, exc: DataGuardError):
    return error_response(exc.status_code, exc.code, exc.message, exc.details)


async def handle_validation_error(request: Request, exc: RequestValidationError):
    errors = [
        {"field": ".".join(str(part) for part in e["loc"]), "message": e["msg"]}
        for e in exc.errors()
    ]
    return error_response(422, "validation_error", "Request validation failed.", {"errors": errors})


async def handle_http_error(request: Request, exc: StarletteHTTPException):
    return error_response(exc.status_code, "http_error", str(exc.detail))


async def handle_unexpected_error(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return error_response(500, "internal_error", "An unexpected error occurred.")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DataGuardError, handle_dataguard_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_error)
    app.add_exception_handler(Exception, handle_unexpected_error)