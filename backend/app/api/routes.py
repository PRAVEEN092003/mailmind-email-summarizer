"""API route controllers for health check, email summarization, authentication, and uploads."""

import logging
import time
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, Query, Path, UploadFile, File, Request
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.errors import (
    RecordNotFoundError,
    AuthenticationError,
    EmailValidationError,
    UserAlreadyExistsError,
    InvalidFileError,
    ForbiddenError,
    RateLimitError,
)
from app.core.security import hash_password, verify_password, create_access_token, validate_password_strength
from app.core.deps import get_current_user, get_optional_user
from app.core.limiter import login_limiter, summarize_limiter, global_limiter, get_request_key
from app.models.database import get_db, SummaryRecord, User
from app.models.schemas import (
    HealthResponse,
    EmailSummarizeRequest,
    EmailSummarizeResponse,
    SummaryHistoryItem,
    SummaryHistoryListResponse,
    DeleteSummaryResponse,
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    TokenResponse,
    EmlParsedInfo,
)
from app.services.ai_service import OllamaService
from app.services.email_service import EmailService
from app.utils.email_parser import parse_eml_bytes, validate_eml_file_upload

router = APIRouter()
logger = logging.getLogger("email_summarizer.routes")

# ---------------------------------------------------------------------------
# Maximum bytes to read incrementally before rejecting oversized uploads.
# Reading in chunks avoids loading an entire multi-MB file into memory before
# applying the size check.
# ---------------------------------------------------------------------------
_CHUNK_SIZE = 64 * 1024  # 64 KB


async def _read_upload_bounded(file: UploadFile, max_bytes: int) -> bytes:
    """Read UploadFile content up to max_bytes without loading the whole file first.

    Raises:
        InvalidFileError: If the stream exceeds max_bytes before EOF.
    """
    chunks: List[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise InvalidFileError(
                message=(
                    f"Uploaded file exceeds the maximum allowed size of "
                    f"{max_bytes // (1024 * 1024)} MB. "
                    "Please upload a smaller .eml file."
                ),
                details={"max_allowed_bytes": max_bytes},
            )
        chunks.append(chunk)
    return b"".join(chunks)


# ---------------------------------------------------------------------------
# Health & Diagnostic Endpoints
# ---------------------------------------------------------------------------

@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint verifying backend, database, and Ollama connectivity."""
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        # Report unhealthy without exposing the raw SQL error chain to callers.
        logger.warning("Database health check failed: %s", exc)
        db_status = "unhealthy"

    ai_service = OllamaService()
    ollama_health = await ai_service.check_health()
    ollama_status = "connected" if ollama_health.get("connected") else "unreachable"

    return HealthResponse(
        status="ok" if db_status == "connected" else "degraded",
        database_status=db_status,
        ollama_status=ollama_status,
        ollama_base_url=settings.OLLAMA_BASE_URL,
        target_model=settings.OLLAMA_MODEL,
        model_available=bool(ollama_health.get("model_available", False)),
        available_models=ollama_health.get("available_models", []),
        schema_version="v3",
        version="1.5.0",
    )


# ---------------------------------------------------------------------------
# User Authentication Endpoints
# ---------------------------------------------------------------------------

@router.post("/auth/register", response_model=TokenResponse, tags=["Authentication"])
async def register_user(
    payload: UserRegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Register a new user account with secure password hashing and return a JWT token."""
    # Apply login/registration rate limit keyed by client IP
    await login_limiter.check(get_request_key(request))

    # Normalise and validate email
    cleaned_email = payload.email.lower().strip()
    if not cleaned_email or "@" not in cleaned_email or "." not in cleaned_email.split("@")[-1]:
        raise AuthenticationError("A valid email address is required.")

    # Enforce password complexity before checking DB so we give useful feedback early
    try:
        validate_password_strength(payload.password)
    except ValueError as exc:
        raise AuthenticationError(str(exc))

    # Check for duplicate registration — isolate DB errors
    try:
        existing_user = db.query(User).filter(User.email == cleaned_email).first()
    except SQLAlchemyError:
        logger.exception("Database error during registration duplicate check")
        raise AuthenticationError("Registration temporarily unavailable. Please try again.")

    if existing_user:
        raise UserAlreadyExistsError(email=cleaned_email)

    # Hash password and persist new account
    hashed_pwd = hash_password(payload.password)
    new_user = User(
        email=cleaned_email,
        hashed_password=hashed_pwd,
        full_name=payload.full_name.strip() if payload.full_name else None,
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error persisting new user")
        raise AuthenticationError("Registration failed due to a server error. Please try again.")

    access_token = create_access_token(
        data={"sub": str(new_user.id), "email": new_user.email}
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=new_user.id,
            email=new_user.email,
            full_name=new_user.full_name,
            created_at=new_user.created_at.isoformat() if new_user.created_at else None,
        ),
    )


@router.post("/auth/login", response_model=TokenResponse, tags=["Authentication"])
async def login_user(
    payload: UserLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Authenticate user with email and password, issuing a signed JWT access token."""
    client_key = get_request_key(request)

    # Strict rate limit before any DB interaction to mitigate brute-force
    await login_limiter.check(client_key)

    cleaned_email = payload.email.lower().strip()

    # Fetch user — always call verify_password even on miss to mitigate timing attacks
    try:
        user = db.query(User).filter(User.email == cleaned_email).first()
    except SQLAlchemyError:
        logger.exception("Database error during login lookup")
        raise AuthenticationError("Login temporarily unavailable. Please try again.")

    dummy_hash = "$2b$12$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    password_ok = verify_password(
        payload.password,
        user.hashed_password if user else dummy_hash,
    )

    if not user or not password_ok:
        raise AuthenticationError("Invalid email or password.")

    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email}
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            created_at=user.created_at.isoformat() if user.created_at else None,
        ),
    )


@router.get("/auth/me", response_model=UserResponse, tags=["Authentication"])
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Retrieve the authenticated user's profile."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        created_at=current_user.created_at.isoformat() if current_user.created_at else None,
    )


@router.post("/auth/logout", tags=["Authentication"])
async def logout_user():
    """Client token discard confirmation (stateless — client must discard the token)."""
    return {"success": True, "message": "Successfully logged out."}


# ---------------------------------------------------------------------------
# Email Upload & Summarization Endpoints
# ---------------------------------------------------------------------------

@router.post("/upload-eml", response_model=EmlParsedInfo, tags=["Upload"])
async def upload_eml_file(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Upload and inspect a standard .eml file, extracting metadata and message body.

    Size is checked incrementally while reading so that oversized uploads are
    rejected without first loading the entire file into RAM.
    """
    # Apply general API rate limit
    await global_limiter.check(get_request_key(request))

    filename = file.filename or "uploaded.eml"

    # Extension validated before we touch the content
    if not filename.lower().endswith(".eml"):
        raise InvalidFileError(
            message="Invalid file format. Only standard email files with .eml extension are supported.",
            details={"filename": filename},
        )

    # Stream-read with early size rejection
    content = await _read_upload_bounded(file, settings.MAX_UPLOAD_SIZE_BYTES)

    # Remaining metadata validation (empty-file guard etc.)
    validate_eml_file_upload(
        filename=filename,
        size=len(content),
        max_bytes=settings.MAX_UPLOAD_SIZE_BYTES,
    )

    parsed_info = parse_eml_bytes(data=content, filename=filename)
    logger.info("EML uploaded: '%s', %d chars extracted", filename, parsed_info["char_count"])

    return EmlParsedInfo(
        filename=parsed_info["filename"],
        subject=parsed_info["subject"],
        from_sender=parsed_info["from_sender"],
        to_recipients=parsed_info["to_recipients"],
        date=parsed_info["date"],
        body=parsed_info["body"],
        char_count=parsed_info["char_count"],
        has_attachments=parsed_info["has_attachments"],
    )


@router.post("/summarize-eml", response_model=EmailSummarizeResponse, tags=["Summarization"])
async def summarize_eml_file(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload, parse, and summarize a .eml file for the authenticated user."""
    # Apply summarize rate limit keyed by user id (more precise than IP for authed users)
    await summarize_limiter.check(f"user:{current_user.id}")

    filename = file.filename or "uploaded.eml"

    if not filename.lower().endswith(".eml"):
        raise InvalidFileError(
            message="Invalid file format. Only .eml files are supported.",
            details={"filename": filename},
        )

    content = await _read_upload_bounded(file, settings.MAX_UPLOAD_SIZE_BYTES)

    validate_eml_file_upload(
        filename=filename,
        size=len(content),
        max_bytes=settings.MAX_UPLOAD_SIZE_BYTES,
    )

    parsed_info = parse_eml_bytes(data=content, filename=filename)
    logger.info(
        "EML summarize upload: '%s', %d chars, user %s",
        filename,
        parsed_info["char_count"],
        current_user.id,
    )

    summarize_request = EmailSummarizeRequest(
        email_content=parsed_info["body"],
        subject=parsed_info["subject"],
    )

    t_endpoint_start = time.perf_counter()
    email_service = EmailService()
    result = await email_service.summarize_email_thread(
        request=summarize_request, db=db, user_id=current_user.id
    )
    endpoint_elapsed_ms = round((time.perf_counter() - t_endpoint_start) * 1000, 2)
    logger.info(
        "TIMING [ENDPOINT] POST /summarize-eml | total_duration=%.2fms | user_id=%s | cached=%s",
        endpoint_elapsed_ms,
        current_user.id,
        result.is_cached,
    )
    return result


@router.post("/summarize", response_model=EmailSummarizeResponse, tags=["Summarization"])
async def summarize_email(
    request: Request,
    payload: EmailSummarizeRequest,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Summarize a pasted email thread with user-scoped caching and ownership."""
    # Rate-limit key: authenticated user id when available, otherwise IP
    rate_key = f"user:{current_user.id}" if current_user else get_request_key(request)
    await summarize_limiter.check(rate_key)

    user_id = current_user.id if current_user else None
    t_endpoint_start = time.perf_counter()
    email_service = EmailService()
    result = await email_service.summarize_email_thread(
        request=payload, db=db, user_id=user_id
    )
    endpoint_elapsed_ms = round((time.perf_counter() - t_endpoint_start) * 1000, 2)
    logger.info(
        "TIMING [ENDPOINT] POST /summarize | total_duration=%.2fms | user_id=%s | cached=%s",
        endpoint_elapsed_ms,
        user_id,
        result.is_cached,
    )
    return result


# ---------------------------------------------------------------------------
# Protected Summary History Endpoints
# ---------------------------------------------------------------------------

@router.get("/history", response_model=SummaryHistoryListResponse, tags=["History"])
async def get_summary_history(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100, description="Max records to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve summary history exclusively owned by the authenticated user."""
    await global_limiter.check(get_request_key(request))

    try:
        total = (
            db.query(func.count(SummaryRecord.id))
            .filter(SummaryRecord.user_id == current_user.id)
            .scalar()
            or 0
        )

        records = (
            db.query(SummaryRecord)
            .filter(SummaryRecord.user_id == current_user.id)
            .order_by(SummaryRecord.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
    except SQLAlchemyError:
        logger.exception("Database error fetching history for user %s", current_user.id)
        raise RecordNotFoundError(message="History is temporarily unavailable. Please try again.")

    items = []
    for r in records:
        items.append(
            SummaryHistoryItem(
                id=r.id,
                user_id=r.user_id,
                content_hash=r.content_hash,
                schema_version=getattr(r, "schema_version", "v3") or "v3",
                subject=r.subject,
                raw_preview=r.raw_content_preview,
                original_content=r.original_content,
                summary=r.get_summary_dict(),
                model_used=r.model_used,
                char_count=r.char_count,
                processing_time_ms=r.processing_time_ms,
                created_at=r.created_at.isoformat() if r.created_at else None,
            )
        )

    return SummaryHistoryListResponse(
        success=True,
        total=total,
        items=items,
    )


@router.get("/history/{summary_id}", response_model=SummaryHistoryItem, tags=["History"])
async def get_summary_by_id(
    request: Request,
    summary_id: int = Path(..., ge=1, description="Unique ID of the summary record"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve an individual summary record, strictly enforcing user ownership."""
    await global_limiter.check(get_request_key(request))

    try:
        record = (
            db.query(SummaryRecord)
            .filter(
                SummaryRecord.id == summary_id,
                SummaryRecord.user_id == current_user.id,
            )
            .first()
        )
    except SQLAlchemyError:
        logger.exception("Database error fetching summary %s for user %s", summary_id, current_user.id)
        raise RecordNotFoundError(message="Summary lookup is temporarily unavailable. Please try again.")

    if not record:
        raise RecordNotFoundError(
            message=f"Summary #{summary_id} was not found or you do not have access to it.",
            details={"summary_id": summary_id},
        )

    return SummaryHistoryItem(
        id=record.id,
        user_id=record.user_id,
        content_hash=record.content_hash,
        schema_version=getattr(record, "schema_version", "v3") or "v3",
        subject=record.subject,
        raw_preview=record.raw_content_preview,
        original_content=record.original_content,
        summary=record.get_summary_dict(),
        model_used=record.model_used,
        char_count=record.char_count,
        processing_time_ms=record.processing_time_ms,
        created_at=record.created_at.isoformat() if record.created_at else None,
    )


@router.delete("/history/{summary_id}", response_model=DeleteSummaryResponse, tags=["History"])
async def delete_summary_by_id(
    request: Request,
    summary_id: int = Path(..., ge=1, description="Unique ID of the summary record to delete"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an individual summary record, strictly enforcing user ownership."""
    await global_limiter.check(get_request_key(request))

    try:
        record = (
            db.query(SummaryRecord)
            .filter(
                SummaryRecord.id == summary_id,
                SummaryRecord.user_id == current_user.id,
            )
            .first()
        )
    except SQLAlchemyError:
        logger.exception("Database error looking up summary %s for deletion", summary_id)
        raise RecordNotFoundError(message="Delete operation is temporarily unavailable. Please try again.")

    if not record:
        raise RecordNotFoundError(
            message=f"Summary #{summary_id} was not found or you do not have access to it.",
            details={"summary_id": summary_id},
        )

    try:
        db.delete(record)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error deleting summary %s", summary_id)
        raise RecordNotFoundError(
            message=f"Failed to delete summary #{summary_id}. Please try again.",
        )

    logger.info("Deleted summary #%s for user %s", summary_id, current_user.id)
    return DeleteSummaryResponse(
        success=True,
        message=f"Summary #{summary_id} deleted successfully.",
        deleted_id=summary_id,
    )


# ---------------------------------------------------------------------------
# Configuration Endpoint
# ---------------------------------------------------------------------------

@router.get("/config", tags=["Configuration"])
async def get_public_config() -> Dict[str, Any]:
    """Retrieve public application configuration (no secrets exposed)."""
    return {
        "model": settings.OLLAMA_MODEL,
        "max_input_chars": settings.MAX_INPUT_CHARS,
        "max_upload_size_bytes": settings.MAX_UPLOAD_SIZE_BYTES,
        "ollama_base_url": settings.OLLAMA_BASE_URL,
    }
