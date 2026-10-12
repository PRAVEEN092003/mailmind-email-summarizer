"""Email parsing and input normalization utilities using Python's standard email library.

Phase 5 hardening:
- validate_eml_file_upload enforces extension and size before any content is processed.
- parse_eml_bytes handles malformed MIME, unsupported encodings, and nested multiparts safely.
- No PII (sender, recipient, subject fragments) is emitted to logs.
- Attachments are strictly skipped; their content is never read or executed.
- Unsupported encodings fall back gracefully via _decode_payload.
"""

import email
import logging
import re
from email import policy
from email.header import decode_header
from email.message import Message
from typing import Dict, Any, Optional
import hashlib

from app.core.errors import EmailValidationError, InvalidFileError

logger = logging.getLogger("email_summarizer.email_parser")


def compute_content_hash(text: str) -> str:
    """Generate a stable SHA-256 hash from normalised email content."""
    normalized = text.strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def validate_email_input(text: Optional[str], max_chars: int = 35_000) -> str:
    """Validate pasted email text: non-empty, minimum length, maximum length.

    Raises:
        EmailValidationError: For empty, too-short, or oversized input.
    """
    if not text or not text.strip():
        raise EmailValidationError(
            "Email content cannot be empty. Please paste an email conversation thread."
        )

    cleaned = text.strip()

    if len(cleaned) < 15:
        raise EmailValidationError(
            "Email content is too short to summarize. "
            "Please paste a substantive email thread."
        )

    if len(cleaned) > max_chars:
        raise EmailValidationError(
            message=(
                f"Email thread exceeds the maximum allowed length of {max_chars:,} characters "
                f"(received {len(cleaned):,} characters). "
                "Please trim earlier message history."
            ),
            details={"max_chars": max_chars, "received_chars": len(cleaned)},
        )

    return cleaned


def clean_pasted_thread(raw_text: str) -> str:
    """Normalise line endings, collapse excessive blank lines, and strip leading/trailing whitespace."""
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse three or more consecutive blank lines into two
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip trailing whitespace from each line but preserve indentation structure
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def _safe_decode_header(val: Optional[str]) -> str:
    """Decode RFC 2047 encoded email header value into clean unicode.

    Falls back to raw string representation on any decoding failure.
    Never raises.
    """
    if not val:
        return ""
    try:
        decoded_parts = decode_header(val)
        result = []
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                enc = encoding or "utf-8"
                try:
                    result.append(part.decode(enc, errors="replace"))
                except LookupError:
                    # Unknown charset — fall back to UTF-8 with replacement chars
                    result.append(part.decode("utf-8", errors="replace"))
            else:
                result.append(str(part))
        return " ".join(result).strip()
    except Exception:
        return str(val)


def validate_eml_file_upload(
    filename: Optional[str], size: int, max_bytes: int = 10 * 1024 * 1024
) -> None:
    """Validate .eml upload metadata: extension, non-empty, and size within limit.

    Must be called *before* parse_eml_bytes.  When used with _read_upload_bounded
    in routes.py the size check here acts as a belt-and-suspenders guard.

    Raises:
        InvalidFileError: For invalid extension, empty file, or oversized file.
    """
    if not filename or not filename.lower().endswith(".eml"):
        raise InvalidFileError(
            message=(
                "Invalid file format. "
                "Only standard email files with .eml extension are supported."
            ),
            details={"filename": filename},
        )

    if size <= 0:
        raise InvalidFileError(
            message="The uploaded .eml file is empty (0 bytes). Please upload a valid email file.",
            details={"size_bytes": size},
        )

    if size > max_bytes:
        raise InvalidFileError(
            message=(
                f"The uploaded file exceeds the maximum allowed size of "
                f"{max_bytes // (1024 * 1024)} MB."
            ),
            details={"size_bytes": size, "max_allowed_bytes": max_bytes},
        )


def parse_eml_bytes(data: bytes, filename: str = "uploaded.eml") -> Dict[str, Any]:
    """Parse RFC-822 / MIME .eml binary data using the Python standard email library.

    Extracts subject, sender, recipient list, date, and readable plain-text body.
    Attachments are strictly skipped and their content is never read or executed.
    Malformed MIME structures and unsupported charsets are handled gracefully.

    Returns:
        Dict with keys: filename, subject, from_sender, to_recipients, date,
        body (str), char_count (int), has_attachments (bool).

    Raises:
        InvalidFileError: For zero-length content, unrecoverable parse failures,
        or when no readable text body can be extracted.
    """
    if not data or len(data.strip()) == 0:
        raise InvalidFileError("Uploaded .eml file has no content.")

    # Parse — try strict policy first, fall back to compat32 for malformed messages
    msg: Optional[Message] = None
    try:
        msg = email.message_from_bytes(data, policy=policy.default)
    except Exception:
        pass

    if msg is None:
        try:
            msg = email.message_from_bytes(data, policy=policy.compat32)
        except Exception:
            raise InvalidFileError(
                "Failed to parse the MIME structure of the uploaded file. "
                "Please verify it is a valid .eml file."
            )

    # Extract and decode headers — handle missing / malformed values gracefully
    try:
        subject = _safe_decode_header(str(msg.get("Subject", "") or ""))
        from_sender = _safe_decode_header(str(msg.get("From", "") or ""))
        to_recipients = _safe_decode_header(str(msg.get("To", "") or ""))
        date_str = str(msg.get("Date", "") or "").strip()
    except Exception:
        subject = from_sender = to_recipients = date_str = ""

    # Extract text body, skipping all attachments
    body, has_attachments = _extract_body(msg)

    cleaned_body = clean_pasted_thread(body)

    if not cleaned_body or len(cleaned_body.strip()) < 10:
        raise InvalidFileError(
            "The uploaded .eml file contains no readable text message body. "
            "Verify that the email is not an empty, encrypted, or attachment-only message."
        )

    # Log only safe, non-PII metadata
    logger.debug(
        "Parsed .eml '%s': body_chars=%d has_attachments=%s",
        filename,
        len(cleaned_body),
        has_attachments,
    )

    return {
        "filename": filename,
        "subject": subject or "Untitled Email (.eml)",
        "from_sender": from_sender or "Unspecified Sender",
        "to_recipients": to_recipients or "Unspecified Recipient",
        "date": date_str or "Unspecified Date",
        "body": cleaned_body,
        "char_count": len(cleaned_body),
        "has_attachments": has_attachments,
    }


def _extract_body(msg: Message) -> tuple:
    """Walk the MIME tree and collect plain-text content; skip all attachments.

    Returns:
        (body_text, has_attachments) — where body_text is the concatenated
        plain-text content from all non-attachment text parts.
    """
    body = ""
    has_attachments = False

    if msg.is_multipart():
        for part in msg.walk():
            try:
                content_type = part.get_content_type()
                disposition = str(part.get("Content-Disposition") or "").lower()

                # Classify as attachment if Content-Disposition says so OR a filename is present
                is_attachment = "attachment" in disposition or bool(part.get_filename())
                if is_attachment:
                    has_attachments = True
                    # Strictly skip — never read attachment content
                    continue

                if content_type == "text/plain":
                    body += _extract_part_text(part)
                elif content_type == "text/html" and not body.strip():
                    # Fall back to HTML → stripped text only when no plain-text part found
                    html_text = _extract_part_text(part)
                    body += _strip_html_tags(html_text)
            except Exception:
                # Malformed individual parts should not abort the whole extraction
                continue
    else:
        try:
            content_type = msg.get_content_type()
            text = _extract_part_text(msg)
            if content_type == "text/html":
                text = _strip_html_tags(text)
            body = text
        except Exception:
            pass

    return body, has_attachments


def _extract_part_text(part: Message) -> str:
    """Extract decoded text from a single MIME part.

    Tries the high-level get_content() first (handles transfer-encoding
    transparently), then falls back to get_payload(decode=True).
    """
    try:
        content = part.get_content()
        if isinstance(content, str):
            return "\n" + content
    except Exception:
        pass

    try:
        payload = part.get_payload(decode=True)
        if payload and isinstance(payload, bytes):
            return "\n" + _decode_payload(payload, part)
    except Exception:
        pass

    return ""


def _decode_payload(payload: bytes, part: Optional[Message] = None) -> str:
    """Decode raw bytes using the part's declared charset, then a fallback chain.

    Never raises; returns a string with replacement characters on total failure.
    """
    # Prefer the charset declared in the Content-Type header
    declared_charset: Optional[str] = None
    if part is not None:
        try:
            declared_charset = part.get_content_charset()
        except Exception:
            pass

    candidates = []
    if declared_charset:
        candidates.append(declared_charset)
    candidates.extend(["utf-8", "latin-1", "windows-1252", "iso-8859-1"])

    for enc in candidates:
        try:
            return payload.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue

    # Last resort — UTF-8 with replacement characters
    return payload.decode("utf-8", errors="replace")


def _strip_html_tags(html: str) -> str:
    """Remove HTML tags and decode common entities for fallback plain-text extraction."""
    text = re.sub(r"<[^>]+>", " ", html)
    replacements = {
        "&amp;": "&", "&lt;": "<", "&gt;": ">",
        "&quot;": '"', "&#39;": "'", "&nbsp;": " ",
    }
    for entity, char in replacements.items():
        text = text.replace(entity, char)
    # Collapse multiple spaces
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text


def inspect_thread_metadata(text: str) -> Dict[str, Any]:
    """Inspect pasted text to detect subject or participant hints if structured headers exist."""
    metadata: Dict[str, Any] = {
        "detected_subject": None,
        "participant_hints": [],
    }

    subject_match = re.search(
        r"^(?:Subject|Re:|Fwd:):\s*(.+)$", text, re.MULTILINE | re.IGNORECASE
    )
    if subject_match:
        metadata["detected_subject"] = subject_match.group(1).strip()

    from_matches = re.findall(
        r"^(?:From|Sent by):\s*(.+)$", text, re.MULTILINE | re.IGNORECASE
    )
    if from_matches:
        metadata["participant_hints"] = [p.strip() for p in from_matches[:10]]

    return metadata
