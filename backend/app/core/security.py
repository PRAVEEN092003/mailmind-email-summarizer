"""Security utilities for password hashing, password validation, and JWT token management."""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
import bcrypt
import jwt

from app.core.config import settings, _MIN_SECRET_LENGTH, _DEFAULT_PLACEHOLDER_SECRET


def validate_jwt_configuration() -> List[str]:
    """Validate JWT configuration at startup; return a list of problem descriptions.

    Returns an empty list when everything is acceptable.
    Callers (the lifespan handler) decide whether to raise or merely warn.
    """
    problems: List[str] = []

    key = settings.JWT_SECRET_KEY
    if not key or len(key) < _MIN_SECRET_LENGTH:
        problems.append(
            f"JWT_SECRET_KEY is too short ({len(key)} chars). "
            f"Minimum required: {_MIN_SECRET_LENGTH} characters."
        )

    if settings.ENVIRONMENT == "production" and key == _DEFAULT_PLACEHOLDER_SECRET:
        problems.append(
            "JWT_SECRET_KEY is still the default placeholder value. "
            "Set a strong, unique secret before deploying to production."
        )

    if settings.JWT_ALGORITHM not in ("HS256", "HS384", "HS512"):
        problems.append(
            f"JWT_ALGORITHM '{settings.JWT_ALGORITHM}' is not a supported HMAC algorithm."
        )

    return problems


def validate_password_strength(password: str) -> None:
    """Enforce configurable password complexity rules.

    Raises:
        ValueError: With a user-readable message listing all unmet requirements.
    """
    errors: List[str] = []

    if len(password) < settings.PASSWORD_MIN_LENGTH:
        errors.append(f"at least {settings.PASSWORD_MIN_LENGTH} characters")

    if settings.PASSWORD_REQUIRE_DIGIT and not re.search(r"\d", password):
        errors.append("at least one digit (0–9)")

    if settings.PASSWORD_REQUIRE_UPPERCASE and not re.search(r"[A-Z]", password):
        errors.append("at least one uppercase letter (A–Z)")

    if settings.PASSWORD_REQUIRE_SPECIAL and not re.search(r"[^A-Za-z0-9]", password):
        errors.append("at least one special character (e.g. !@#$%)")

    if errors:
        raise ValueError("Password must contain: " + ", ".join(errors) + ".")


def hash_password(password: str) -> str:
    """Hash a plaintext password securely using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify that a plaintext password matches the stored bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def create_access_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """Create a signed JWT access token containing the provided claims plus exp/iat."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "iat": now})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """Verify and decode a JWT access token.

    Validates signature, expiration, and that required claims ('sub') are present.

    Raises:
        AuthenticationError: For expired, tampered, or structurally invalid tokens.
    """
    # Import here to avoid circular imports (errors -> config -> security)
    from app.core.errors import AuthenticationError

    if not token or not token.strip():
        raise AuthenticationError("No access token provided.")

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Access token has expired. Please log in again.")
    except jwt.MissingRequiredClaimError as exc:
        raise AuthenticationError(f"Token is missing a required claim: {exc}.")
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError(f"Invalid access token: {exc}.")

    # Belt-and-suspenders: ensure 'sub' is non-empty even if jwt.decode passed
    sub = payload.get("sub")
    if not sub or not str(sub).strip():
        raise AuthenticationError("Token payload is missing a valid user identity ('sub').")

    return payload
