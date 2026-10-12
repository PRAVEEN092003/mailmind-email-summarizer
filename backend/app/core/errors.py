"""Application custom exceptions and error models."""

from typing import Any, Optional
from fastapi import Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger("email_summarizer.errors")


class AppError(Exception):
    """Base application exception."""

    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Optional[Any] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class OllamaConnectionError(AppError):
    """Raised when Ollama daemon cannot be reached."""

    def __init__(
        self,
        message: str = "Ollama service is unreachable. Please ensure Ollama is installed and running (e.g. `ollama serve`).",
        details: Optional[Any] = None,
    ):
        super().__init__(
            message=message,
            error_code="OLLAMA_SERVICE_UNAVAILABLE",
            status_code=503,
            details=details,
        )


class OllamaModelNotFoundError(AppError):
    """Raised when the specified model is not found in Ollama."""

    def __init__(
        self,
        model_name: str,
        message: Optional[str] = None,
        details: Optional[Any] = None,
    ):
        msg = (
            message
            or f"Ollama model '{model_name}' was not found. Please pull the model using `ollama pull {model_name}`."
        )
        super().__init__(
            message=msg,
            error_code="OLLAMA_MODEL_NOT_FOUND",
            status_code=404,
            details={"model": model_name, **(details or {})},
        )


class OllamaTimeoutError(AppError):
    """Raised when Ollama generation times out."""

    def __init__(
        self,
        message: str = "Ollama model inference timed out. Please try with shorter content or increase timeout.",
        details: Optional[Any] = None,
    ):
        super().__init__(
            message=message,
            error_code="OLLAMA_TIMEOUT",
            status_code=504,
            details=details,
        )


class OllamaResponseFormatError(AppError):
    """Raised when Ollama output cannot be parsed into the expected JSON structure."""

    def __init__(
        self,
        message: str = "Failed to parse structured summary from the AI model response.",
        raw_output: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            error_code="OLLAMA_INVALID_FORMAT",
            status_code=502,
            details={"raw_output_snippet": (raw_output[:500] if raw_output else None)},
        )


class EmailValidationError(AppError):
    """Raised when input email thread violates validation rules."""

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            error_code="EMAIL_VALIDATION_ERROR",
            status_code=422,
            details=details,
        )


class RecordNotFoundError(AppError):
    """Raised when a requested resource or summary record is not found."""

    def __init__(self, message: str = "Resource not found.", details: Optional[Any] = None):
        super().__init__(
            message=message,
            error_code="NOT_FOUND",
            status_code=404,
            details=details,
        )


class AuthenticationError(AppError):
    """Raised when authentication credentials are missing or invalid."""

    def __init__(self, message: str = "Authentication failed. Invalid or expired token.", details: Optional[Any] = None):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_FAILED",
            status_code=401,
            details=details,
        )


class ForbiddenError(AppError):
    """Raised when user lacks permission to access a specific resource."""

    def __init__(self, message: str = "Access forbidden. You do not own this resource.", details: Optional[Any] = None):
        super().__init__(
            message=message,
            error_code="ACCESS_FORBIDDEN",
            status_code=403,
            details=details,
        )


class UserAlreadyExistsError(AppError):
    """Raised during registration if the email is already taken."""

    def __init__(self, email: str, message: Optional[str] = None):
        super().__init__(
            message=message or f"An account with email '{email}' already exists.",
            error_code="USER_ALREADY_EXISTS",
            status_code=409,
            details={"email": email},
        )


class InvalidFileError(AppError):
    """Raised when uploaded file is invalid, oversized, or unreadable."""

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            error_code="INVALID_FILE",
            status_code=400,
            details=details,
        )


class RateLimitError(AppError):
    """Raised when a client exceeds the configured request-rate budget."""

    def __init__(
        self,
        message: str = "Too many requests. Please slow down and try again later.",
        retry_after: Optional[int] = None,
        details: Optional[Any] = None,
    ):
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            details=details,
        )
        # Seconds until the client may retry — surfaced via Retry-After header.
        self.retry_after: Optional[int] = retry_after


class ConfigurationError(AppError):
    """Raised at startup when a required configuration value is missing or insecure."""

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            error_code="CONFIGURATION_ERROR",
            status_code=500,
            details=details,
        )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """FastAPI handler for custom AppError exceptions — always returns structured JSON."""
    headers: dict = {}

    # Attach Retry-After header for rate-limit errors so HTTP clients can back off.
    retry_after = getattr(exc, "retry_after", None)
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)

    # Log server-side errors at WARNING level; client errors at DEBUG.
    if exc.status_code >= 500:
        logger.error(
            "Server error [%s] %s on %s %s",
            exc.error_code,
            exc.message,
            request.method,
            request.url.path,
        )
    else:
        logger.debug(
            "Client error [%s] %s on %s %s",
            exc.error_code,
            exc.message,
            request.method,
            request.url.path,
        )

    return JSONResponse(
        status_code=exc.status_code,
        headers=headers,
        content={
            "success": False,
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details,
        },
    )
