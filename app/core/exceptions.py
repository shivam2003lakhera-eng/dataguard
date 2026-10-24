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


class ConfigurationError(DataGuardError):
    code = "invalid_configuration"
    status_code = 422


class UnsupportedFormatError(DataGuardError):
    code = "unsupported_format"
    status_code = 422


class InvalidSourceDataError(DataGuardError):
    code = "invalid_source_data"
    status_code = 422


class FileTooLargeError(DataGuardError):
    code = "file_too_large"
    status_code = 413



class AuthenticationError(DataGuardError):
    code = "not_authenticated"
    status_code = 401


class InvalidCredentialsError(AuthenticationError):
    code = "invalid_credentials"


class ConflictError(DataGuardError):
    code = "conflict"
    status_code = 409


class RegistrationClosedError(DataGuardError):
    code = "registration_closed"
    status_code = 403


class TooManyAttemptsError(DataGuardError):
    code = "too_many_attempts"
    status_code = 429