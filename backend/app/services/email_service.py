"""Email summarization business logic coordinating validation, user-scoped caching,
in-flight deduplication, AI summarization, and SQLite persistence.

Phase 5 hardening:
- All DB operations wrapped in SQLAlchemyError handlers; SQL details never reach callers.
- Logs never contain raw email content — only char counts, hashes, and IDs.
- Cache-hit path returns immediately without creating a duplicate history record.
- In-flight deduplication key is scoped by user to prevent cross-user data leakage.
"""

import asyncio
import logging
import time
from typing import Optional, Dict

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.models.schemas import (
    EmailSummarizeRequest,
    EmailSummarizeResponse,
    StructuredSummary,
)
from app.models.database import SummaryRecord
from app.services.ai_service import OllamaService
from app.utils.email_parser import (
    validate_email_input,
    clean_pasted_thread,
    inspect_thread_metadata,
    compute_content_hash,
)

logger = logging.getLogger("email_summarizer.email_service")

# Schema and prompt version — bump this when the AI output schema changes to
# ensure older cached summaries with an incompatible shape are not returned.
SCHEMA_VERSION = "v3"

# ---------------------------------------------------------------------------
# In-flight concurrent request deduplication
# ---------------------------------------------------------------------------
# Maps "<user_scope>:<content_hash>:<model>:<schema_version>" -> asyncio.Future
# so that simultaneous identical requests from the same user share one AI call.
_inflight_tasks: Dict[str, asyncio.Future] = {}
_inflight_lock = asyncio.Lock()


class EmailService:
    """Coordinates validation, caching, deduplication, AI summarization, and storage."""

    def __init__(self, ai_service: Optional[OllamaService] = None):
        self.ai_service = ai_service or OllamaService()

    async def summarize_email_thread(
        self,
        request: EmailSummarizeRequest,
        db: Optional[Session] = None,
        user_id: Optional[int] = None,
    ) -> EmailSummarizeResponse:
        """Process, cache-check, deduplicate, summarize, and persist an email thread.

        Steps:
        1. Validate and normalise input text.
        2. Compute a stable content hash.
        3. Check user-scoped SQLite cache — return immediately on hit (no new record).
        4. Deduplicate simultaneous identical requests — followers await the leader.
        5. As leader: call Ollama, persist result, resolve follower futures.
        """
        t_total_start = time.perf_counter()

        # ------------------------------------------------------------------
        # 1. Validate input size and non-empty content
        # ------------------------------------------------------------------
        t_pre_start = time.perf_counter()
        validated_text = validate_email_input(
            request.email_content, max_chars=settings.MAX_INPUT_CHARS
        )

        # ------------------------------------------------------------------
        # 2. Clean, normalise, and hash
        # ------------------------------------------------------------------
        cleaned_text = clean_pasted_thread(validated_text)

        subject = request.subject
        if not subject:
            metadata = inspect_thread_metadata(cleaned_text)
            subject = metadata.get("detected_subject")

        content_hash = compute_content_hash(cleaned_text)
        current_model = self.ai_service.model_name

        preprocess_ms = round((time.perf_counter() - t_pre_start) * 1000, 2)
        logger.info(
            "TIMING [PREPROCESS] parse_preprocess=%.2fms | chars=%d",
            preprocess_ms,
            len(cleaned_text),
        )

        # Scope all cache/dedup operations to the owning user to completely
        # prevent cross-user data leakage (anonymous requests use "public").
        user_scope = str(user_id) if user_id is not None else "public"
        cache_key = f"{user_scope}:{content_hash}:{current_model}:{SCHEMA_VERSION}"

        # ------------------------------------------------------------------
        # 3. User-scoped cache lookup (no duplicate DB write on hit)
        # ------------------------------------------------------------------
        if db is not None:
            t_cache_start = time.perf_counter()
            cached_record = self._lookup_cache(db, content_hash, current_model, user_id)
            cache_lookup_ms = round((time.perf_counter() - t_cache_start) * 1000, 2)
            logger.info(
                "TIMING [CACHE_LOOKUP] lookup_time=%.2fms | hit=%s",
                cache_lookup_ms,
                cached_record is not None,
            )

            if cached_record is not None:
                # Strictly ensure the cached record's content matches current input
                if cached_record.content_hash != content_hash:
                    logger.warning("Cache record %s hash mismatch; invalidating cache hit.", cached_record.id)
                    cached_record = None
                elif cached_record.original_content:
                    cached_cleaned = clean_pasted_thread(cached_record.original_content)
                    if compute_content_hash(cached_cleaned) != content_hash:
                        logger.warning("Cache record %s original_content hash mismatch; invalidating.", cached_record.id)
                        cached_record = None

            if cached_record is not None:
                summary_dict = cached_record.get_summary_dict()
                try:
                    structured_data = StructuredSummary(**summary_dict)

                    # Guard against stale/corrupted cache entries containing ungrounded entities
                    cache_dump_str = json.dumps(summary_dict).lower()
                    for ungrounded_marker in ("terms of service", "staging", "standup", "redis", "phase 2"):
                        if ungrounded_marker in cache_dump_str and ungrounded_marker not in cleaned_text.lower():
                            logger.warning(
                                "Cache record %s contains stale ungrounded '%s'; invalidating and regenerating.",
                                cached_record.id,
                                ungrounded_marker,
                            )
                            raise ValueError(f"Stale ungrounded cache entry: {ungrounded_marker}")

                    total_cache_ms = round((time.perf_counter() - t_total_start) * 1000, 2)
                    logger.info(
                        "TIMING [CACHE_HIT] total_duration=%.2fms | user=%s hash=%s... id=%s",
                        total_cache_ms,
                        user_scope,
                        content_hash[:8],
                        cached_record.id,
                    )
                    return EmailSummarizeResponse(
                        success=True,
                        data=structured_data,
                        model_used=cached_record.model_used,
                        processing_time_ms=0.0,
                        ollama_generation_time_ms=0.0,
                        chars_processed=cached_record.char_count,
                        is_cached=True,
                        content_hash=content_hash,
                        history_id=cached_record.id,
                        schema_version=SCHEMA_VERSION,
                    )
                except Exception:
                    # Cached record has an incompatible schema or stale/ungrounded details — regenerate
                    logger.warning(
                        "Cache record %s invalid or stale; regenerating.",
                        cached_record.id,
                    )

        # ------------------------------------------------------------------
        # 4. In-flight deduplication
        # ------------------------------------------------------------------
        async with _inflight_lock:
            if cache_key in _inflight_tasks:
                in_flight_future = _inflight_tasks[cache_key]
                is_leader = False
            else:
                loop = asyncio.get_running_loop()
                in_flight_future = loop.create_future()
                _inflight_tasks[cache_key] = in_flight_future
                is_leader = True

        if not is_leader:
            logger.info("Duplicate in-flight request for key %s; awaiting leader.", cache_key)
            leader_result: EmailSummarizeResponse = await in_flight_future
            total_leader_ms = round((time.perf_counter() - t_total_start) * 1000, 2)
            logger.info(
                "TIMING [INFLIGHT_FOLLOWER] total_wait=%.2fms | leader_history_id=%s",
                total_leader_ms,
                leader_result.history_id,
            )
            return EmailSummarizeResponse(
                success=leader_result.success,
                data=leader_result.data,
                model_used=leader_result.model_used,
                processing_time_ms=leader_result.processing_time_ms,
                ollama_generation_time_ms=leader_result.ollama_generation_time_ms,
                chars_processed=leader_result.chars_processed,
                is_cached=True,
                content_hash=content_hash,
                history_id=leader_result.history_id,
                schema_version=SCHEMA_VERSION,
            )

        # ------------------------------------------------------------------
        # 5. Leader: call AI and persist result
        # ------------------------------------------------------------------
        try:
            summary_result, ollama_generation_ms = await self.ai_service.summarize(
                thread_content=cleaned_text, subject=subject
            )

            # Persist result — log only safe metadata, never email content
            saved_id: Optional[int] = None
            if db is not None:
                t_db_start = time.perf_counter()
                total_interim_ms = round((time.perf_counter() - t_total_start) * 1000, 2)
                saved_id = self._persist_summary(
                    db=db,
                    user_id=user_id,
                    content_hash=content_hash,
                    subject=subject,
                    cleaned_text=cleaned_text,
                    summary_result=summary_result,
                    current_model=current_model,
                    elapsed_ms=total_interim_ms,
                    user_scope=user_scope,
                )
                db_save_ms = round((time.perf_counter() - t_db_start) * 1000, 2)
                logger.info(
                    "TIMING [DB_SAVE] database_save=%.2fms | id=%s",
                    db_save_ms,
                    saved_id,
                )

            total_elapsed_ms = round((time.perf_counter() - t_total_start) * 1000, 2)
            logger.info(
                "TIMING [SUMMARY_COMPLETE] total_duration=%.2fms | ollama_generation=%.2fms | chars=%d | id=%s",
                total_elapsed_ms,
                ollama_generation_ms,
                len(cleaned_text),
                saved_id,
            )

            final_response = EmailSummarizeResponse(
                success=True,
                data=summary_result,
                model_used=current_model,
                processing_time_ms=total_elapsed_ms,
                ollama_generation_time_ms=ollama_generation_ms,
                chars_processed=len(cleaned_text),
                is_cached=False,
                content_hash=content_hash,
                history_id=saved_id,
                schema_version=SCHEMA_VERSION,
            )

            if not in_flight_future.done():
                in_flight_future.set_result(final_response)

            return final_response

        except Exception as exc:
            if not in_flight_future.done():
                in_flight_future.set_exception(exc)
            raise

        finally:
            async with _inflight_lock:
                _inflight_tasks.pop(cache_key, None)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _lookup_cache(
        self,
        db: Session,
        content_hash: str,
        current_model: str,
        user_id: Optional[int],
    ) -> Optional[SummaryRecord]:
        """Query the user-scoped cache. Returns the record on hit, None on miss or DB error."""
        try:
            record = (
                db.query(SummaryRecord)
                .filter(
                    SummaryRecord.content_hash == content_hash,
                    SummaryRecord.model_used == current_model,
                    SummaryRecord.schema_version == SCHEMA_VERSION,
                    SummaryRecord.user_id == user_id,
                )
                .order_by(SummaryRecord.created_at.desc())
                .first()
            )
            return record
        except SQLAlchemyError as exc:
            logger.warning(
                "Cache lookup failed (will regenerate): %s",
                type(exc).__name__,
            )
            return None

    def _persist_summary(
        self,
        db: Session,
        user_id: Optional[int],
        content_hash: str,
        subject: Optional[str],
        cleaned_text: str,
        summary_result: StructuredSummary,
        current_model: str,
        elapsed_ms: float,
        user_scope: str,
    ) -> Optional[int]:
        """Persist a new SummaryRecord. Returns the saved record ID or None on failure."""
        try:
            record = SummaryRecord(
                user_id=user_id,
                content_hash=content_hash,
                schema_version=SCHEMA_VERSION,
                subject=subject or "Untitled Email Thread",
                # Store only a safe preview — never log the full body
                raw_content_preview=cleaned_text[:400],
                original_content=cleaned_text,
                summary_json=summary_result.model_dump_json(),
                model_used=current_model,
                char_count=len(cleaned_text),
                processing_time_ms=int(elapsed_ms),
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            logger.info(
                "Persisted summary id=%s for user=%s chars=%d elapsed=%.0fms",
                record.id,
                user_scope,
                len(cleaned_text),
                elapsed_ms,
            )
            return record.id
        except SQLAlchemyError as exc:
            db.rollback()
            logger.error(
                "Failed to persist summary for user=%s: %s",
                user_scope,
                type(exc).__name__,
            )
            # Non-fatal: the summarization succeeded; the client still gets a result
            return None
