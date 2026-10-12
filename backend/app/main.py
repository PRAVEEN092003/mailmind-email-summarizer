"""FastAPI application entrypoint for Intelligent Email Thread Summarizer."""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.errors import AppError, RateLimitError, app_error_handler
from app.core.security import validate_jwt_configuration
from app.models.database import init_db
from app.services.ai_service import close_ai_client
from app.api.routes import router as api_router

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
# Use a format that includes level, logger name, and message but deliberately
# omits request bodies so private email content never reaches log sinks.
logging.basicConfig(
    level=logging.DEBUG if settings.ENVIRONMENT == "development" else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("email_summarizer")


# ---------------------------------------------------------------------------
# Application lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle event handler: validates configuration, initialises database."""

    # ---- Startup configuration validation ----
    jwt_problems = validate_jwt_configuration()
    if jwt_problems:
        for problem in jwt_problems:
            if settings.ENVIRONMENT == "production":
                # Hard-fail in production so a misconfigured deployment is caught
                # before serving any requests.
                logger.critical("FATAL configuration error: %s", problem)
                raise SystemExit(
                    f"[FATAL] Authentication configuration is insecure: {problem}"
                )
            else:
                logger.warning("Configuration warning: %s", problem)

    # ---- Database initialisation ----
    logger.info("Initialising SQLite database tables…")
    try:
        init_db()
    except Exception as exc:
        logger.critical("Database initialisation failed: %s", exc)
        raise SystemExit(f"[FATAL] Cannot initialise database: {exc}") from exc

    logger.info(
        "Application ready. Ollama endpoint: %s (model: %s, max_concurrent: %s)",
        settings.OLLAMA_BASE_URL,
        settings.OLLAMA_MODEL,
        settings.OLLAMA_MAX_CONCURRENT,
    )
    yield
    logger.info("Application shutting down. Closing Ollama persistent client...")
    await close_ai_client()
    logger.info("Application shutdown complete.")


# ---------------------------------------------------------------------------
# FastAPI app instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Intelligent Email Thread Summarizer for Overwhelmed Users — "
        "Phase 5 hardened backend"
    ),
    version="1.5.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

# All AppError subclasses (including RateLimitError) are handled here.
# The handler sets the correct HTTP status code and Retry-After header.
app.add_exception_handler(AppError, app_error_handler)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Fallback handler for unhandled exceptions.

    Stack traces are logged server-side; the client receives a safe, opaque
    message with no internal implementation details.
    """
    logger.error(
        "Unhandled exception on %s %s",
        request.method,
        request.url.path,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected server error occurred. Please try again later.",
            # No 'details' key — never expose internal errors to clients.
        },
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

# Mount routes under /api prefix (primary) and at root (health / backwards compat)
app.include_router(api_router, prefix=settings.API_V1_STR)
app.include_router(api_router, prefix="")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
