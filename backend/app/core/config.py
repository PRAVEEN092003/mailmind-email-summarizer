"""Application configuration module."""

import json
import secrets
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Minimum acceptable JWT secret length (characters).  Shorter secrets are
# rejected at startup so that developers notice immediately instead of
# silently running with an insecure configuration.
_MIN_SECRET_LENGTH = 32

# The well-known placeholder value shipped in .env.example / initial .env.
# Startup validation rejects this value when ENVIRONMENT == "production".
_DEFAULT_PLACEHOLDER_SECRET = (
    "supersecret-jwt-key-for-local-email-summarizer-change-in-prod"
)


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    PROJECT_NAME: str = "Intelligent Email Thread Summarizer"
    API_V1_STR: str = "/api"

    # Deployment environment: "development" (default) or "production"
    ENVIRONMENT: str = "development"

    # ---------------------------------------------------------------------------
    # Ollama settings
    # ---------------------------------------------------------------------------
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b"
    OLLAMA_TIMEOUT_SECONDS: int = 240
    #: Maximum simultaneous inference requests forwarded to Ollama.
    #: Prevents exhausting CPU/RAM on resource-constrained laptops.
    OLLAMA_MAX_CONCURRENT: int = 2
    #: Keep model loaded in memory across requests to prevent cold reload latency.
    OLLAMA_KEEP_ALIVE: str = "1h"
    #: Bounded generation token limit for structured JSON summary.
    OLLAMA_MAX_PREDICT: int = 500
    #: Deterministic decoding temperature.
    OLLAMA_TEMPERATURE: float = 0.0
    #: Context window token size.
    OLLAMA_NUM_CTX: int = 2048

    # ---------------------------------------------------------------------------
    # Input / upload size constraints
    # ---------------------------------------------------------------------------
    MAX_INPUT_CHARS: int = 35_000
    MAX_UPLOAD_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB

    # ---------------------------------------------------------------------------
    # CORS settings
    # ---------------------------------------------------------------------------
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    # ---------------------------------------------------------------------------
    # Database settings
    # ---------------------------------------------------------------------------
    DATABASE_URL: str = "sqlite:///./email_summarizer.db"

    # ---------------------------------------------------------------------------
    # Authentication & JWT settings
    # ---------------------------------------------------------------------------
    JWT_SECRET_KEY: str = _DEFAULT_PLACEHOLDER_SECRET
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # ---------------------------------------------------------------------------
    # Password requirements
    # ---------------------------------------------------------------------------
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_REQUIRE_DIGIT: bool = True
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_SPECIAL: bool = False  # relaxed for local use

    # ---------------------------------------------------------------------------
    # Rate limiting
    # ---------------------------------------------------------------------------
    #: Login endpoint: max attempts per window to mitigate brute-force.
    RATE_LIMIT_LOGIN_MAX: int = 10
    RATE_LIMIT_LOGIN_WINDOW_SECONDS: int = 300  # 5 minutes

    #: AI summarisation: prevents runaway Ollama usage per client.
    RATE_LIMIT_SUMMARIZE_MAX: int = 20
    RATE_LIMIT_SUMMARIZE_WINDOW_SECONDS: int = 3600  # 1 hour

    #: General API limiter – applied to all other routes.
    RATE_LIMIT_GLOBAL_MAX: int = 200
    RATE_LIMIT_GLOBAL_WINDOW_SECONDS: int = 60  # per minute

    # ---------------------------------------------------------------------------
    # Validators
    # ---------------------------------------------------------------------------

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
