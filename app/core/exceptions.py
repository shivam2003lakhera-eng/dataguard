from typing import Any


class DataGuardError(Exception):
    """Base class for all errors DataGuard raises on purpose."""

    code = "internal_error"
    status_code = 500

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(DataGuardError):
    code = "not_found"
    status_code = 404


class ConflictError(DataGuardError):
    code = "conflict"
    status_code = 409


class ConfigurationError(DataGuardError):
    code = "invalid_configuration"
    status_code = 422


class SourceFileNotFoundError(DataGuardError):
    code = "source_file_not_found"
    status_code = 404


class UnsupportedFormatError(DataGuardError):
    code = "unsupported_format"
    status_code = 422


class InvalidSourceDataError(DataGuardError):
    code = "invalid_source_data"
    status_code = 422


class FileTooLargeError(DataGuardError):
    code = "file_too_large"
    status_code = 413


class AccessDeniedError(DataGuardError):
    code = "access_denied"
    status_code = 403