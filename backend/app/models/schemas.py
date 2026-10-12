"""Pydantic schemas for request validation, structured summaries, authentication, and uploads."""

from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, model_validator


class ActionItem(BaseModel):
    """Specific task or action item extracted from the thread with execution status."""

    item: str = Field(description="Actionable task description")
    responsible_person: Optional[str] = Field(
        default=None,
        description="Explicitly identified person responsible, or None if unspecified",
    )
    deadline: Optional[str] = Field(
        default=None,
        description="Explicit deadline date/time for this task, or None if not stated",
    )
    status: str = Field(
        default="pending",
        description="Task status: 'completed', 'pending', or 'uncertain'",
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_action_item(cls, data: Any) -> Any:
        if isinstance(data, dict):
            status_val = str(data.get("status") or "pending").lower().strip()
            if status_val in ("completed", "done", "finished"):
                data["status"] = "completed"
            elif status_val in ("uncertain", "blocked", "tentative", "unknown"):
                data["status"] = "uncertain"
            else:
                data["status"] = "pending"

            # Normalize string representations of null/none/unspecified
            for field in ("responsible_person", "deadline"):
                val = data.get(field)
                if isinstance(val, str) and val.strip().lower() in ("null", "none", "unassigned", "not specified", "n/a", "undefined", ""):
                    data[field] = None
        return data


class StructuredSummary(BaseModel):
    """Complete structured breakdown of the email conversation with urgency and confirmed decisions."""

    overall_summary: str = Field(
        description="Concise synthesis of the email thread context and current status"
    )
    main_discussion_points: List[str] = Field(
        default_factory=list,
        description="Key arguments, updates, or topics addressed by participants",
    )
    confirmed_decisions: List[str] = Field(
        default_factory=list,
        description="Explicitly agreed-upon and confirmed decisions with context",
    )
    important_decisions: List[str] = Field(
        default_factory=list,
        description="Backward-compatible alias for confirmed decisions",
    )
    action_items: List[ActionItem] = Field(
        default_factory=list,
        description="Concrete next steps or tasks with assignees, deadlines, and statuses",
    )
    responsible_persons: List[str] = Field(
        default_factory=list,
        description="Distinct participants explicitly assigned duties or roles",
    )
    deadlines: List[str] = Field(
        default_factory=list,
        description="Explicit deadlines or milestones mentioned",
    )
    unanswered_questions: List[str] = Field(
        default_factory=list,
        description="Questions asked in the thread that received no answer or resolution",
    )
    urgency_level: str = Field(
        default="MEDIUM",
        description="Thread priority: 'HIGH', 'MEDIUM', or 'LOW'",
    )
    urgency_explanation: str = Field(
        default="Standard discussion thread without emergency escalations.",
        description="Concise rationale for urgency classification",
    )

    @model_validator(mode="before")
    @classmethod
    def sync_decisions_and_urgency(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Synchronize confirmed_decisions and important_decisions
            confirmed = data.get("confirmed_decisions")
            important = data.get("important_decisions")
            if confirmed and not important:
                data["important_decisions"] = confirmed
            elif important and not confirmed:
                data["confirmed_decisions"] = important

            # Normalize urgency level
            raw_urgency = str(data.get("urgency_level") or "MEDIUM").upper().strip()
            if raw_urgency in ("HIGH", "CRITICAL", "URGENT"):
                data["urgency_level"] = "HIGH"
            elif raw_urgency in ("LOW", "MINOR"):
                data["urgency_level"] = "LOW"
            else:
                data["urgency_level"] = "MEDIUM"

            if not data.get("urgency_explanation"):
                data["urgency_explanation"] = (
                    "Routine business correspondence."
                    if data["urgency_level"] != "HIGH"
                    else "High urgency detected based on deadlines or stated consequences."
                )

            # Sanitize responsible_persons and deadlines
            if "responsible_persons" in data and isinstance(data["responsible_persons"], list):
                clean_p = []
                for p in data["responsible_persons"]:
                    if isinstance(p, str) and p.strip().lower() not in ("null", "none", "unassigned", "n/a", ""):
                        clean_p.append(p.strip())
                data["responsible_persons"] = clean_p

            if "deadlines" in data and isinstance(data["deadlines"], list):
                clean_d = []
                for d in data["deadlines"]:
                    if isinstance(d, str) and d.strip().lower() not in ("null", "none", "not specified", "n/a", ""):
                        clean_d.append(d.strip())
                data["deadlines"] = clean_d

        return data


# --- User Authentication Schemas ---

class UserRegisterRequest(BaseModel):
    """User registration request payload."""

    email: str = Field(..., description="Unique email address")
    password: str = Field(..., min_length=6, description="Password with minimum 6 characters")
    full_name: Optional[str] = Field(default=None, description="Optional full name")


class UserLoginRequest(BaseModel):
    """User login credential payload."""

    email: str = Field(..., description="Account email address")
    password: str = Field(..., description="Account password")


class UserResponse(BaseModel):
    """User profile response without sensitive credentials."""

    id: int
    email: str
    full_name: Optional[str] = None
    created_at: Optional[str] = None


class TokenResponse(BaseModel):
    """JWT access token response."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# --- Summarization and EML Upload Schemas ---

class EmailSummarizeRequest(BaseModel):
    """Input payload for email thread summarization."""

    email_content: str = Field(
        ...,
        description="Raw text or formatted content of the email conversation thread",
    )
    subject: Optional[str] = Field(
        default=None,
        description="Optional subject line of the email thread",
    )


class EmlParsedInfo(BaseModel):
    """Extracted metadata and plain-text body from an uploaded .eml file."""

    filename: str
    subject: str
    from_sender: str
    to_recipients: str
    date: str
    body: str
    char_count: int
    has_attachments: bool


class EmailSummarizeResponse(BaseModel):
    """Response containing the structured summary, cache status, and execution metadata."""

    success: bool = True
    data: Optional[StructuredSummary] = None
    model_used: Optional[str] = None
    processing_time_ms: Optional[float] = None
    ollama_generation_time_ms: Optional[float] = None
    chars_processed: Optional[int] = None
    is_cached: bool = False
    content_hash: Optional[str] = None
    history_id: Optional[int] = None
    schema_version: Optional[str] = "v3"
    error: Optional[str] = None


class SummaryHistoryItem(BaseModel):
    """Single summary record item returned in history queries."""

    id: int
    user_id: Optional[int] = None
    content_hash: Optional[str] = None
    subject: Optional[str] = None
    raw_preview: str
    original_content: Optional[str] = None
    summary: StructuredSummary
    model_used: str
    char_count: int
    processing_time_ms: Optional[int] = None
    schema_version: Optional[str] = "v3"
    created_at: Optional[str] = None


class SummaryHistoryListResponse(BaseModel):
    """Paginated list response of summary history records."""

    success: bool = True
    total: int
    items: List[SummaryHistoryItem] = Field(default_factory=list)


class DeleteSummaryResponse(BaseModel):
    """Response payload following a summary deletion."""

    success: bool = True
    message: str
    deleted_id: int


class HealthResponse(BaseModel):
    """Service health and connection diagnostic report."""

    status: str = "ok"
    database_status: str
    ollama_status: str
    ollama_base_url: str
    target_model: str
    model_available: bool
    available_models: List[str] = Field(default_factory=list)
    schema_version: str = "v3"
    version: str = "1.0.0"
