"""In-memory sliding-window rate limiter for login and AI summarization endpoints.

Designed for single-instance SQLite deployments. No external dependencies required.
All state is process-local; limits reset on server restart which is acceptable for
a local application.
"""

import asyncio
import time
from collections import defaultdict, deque
from typing import Dict, Deque

from app.core.config import settings
from app.core.errors import RateLimitError


class SlidingWindowRateLimiter:
    """Thread-safe async sliding-window rate limiter keyed by a string identifier.

    Maintains a deque of request timestamps per key; evicts entries older than
    ``window_seconds`` before each check. No background cleanup task is needed
    because eviction happens on every request.
    """

    def __init__(self, max_requests: int, window_seconds: int, endpoint_name: str = ""):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.endpoint_name = endpoint_name
        self._timestamps: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> None:
        """Raise RateLimitError if the key has exceeded its request budget.

        Args:
            key: A per-client or per-user string identifier (e.g. IP address or user id).

        Raises:
            RateLimitError: When the sliding window budget is exhausted.
        """
        async with self._lock:
            now = time.monotonic()
            window_start = now - self.window_seconds
            dq = self._timestamps[key]

            # Evict timestamps outside the current window
            while dq and dq[0] < window_start:
                dq.popleft()

            if len(dq) >= self.max_requests:
                retry_after = int(self.window_seconds - (now - dq[0])) + 1
                endpoint_label = f" on {self.endpoint_name}" if self.endpoint_name else ""
                raise RateLimitError(
                    message=(
                        f"Too many requests{endpoint_label}. "
                        f"Limit: {self.max_requests} per {self.window_seconds}s window."
                    ),
                    retry_after=retry_after,
                )

            dq.append(now)

    async def reset(self, key: str) -> None:
        """Clear all rate-limit state for a key (e.g. after successful login)."""
        async with self._lock:
            self._timestamps.pop(key, None)


# ---------------------------------------------------------------------------
# Shared rate-limiter singletons
# ---------------------------------------------------------------------------

#: Strict limiter for login — prevents brute-force attacks.
login_limiter = SlidingWindowRateLimiter(
    max_requests=settings.RATE_LIMIT_LOGIN_MAX,
    window_seconds=settings.RATE_LIMIT_LOGIN_WINDOW_SECONDS,
    endpoint_name="login",
)

#: Per-user/IP limiter for the AI summarization endpoints.
summarize_limiter = SlidingWindowRateLimiter(
    max_requests=settings.RATE_LIMIT_SUMMARIZE_MAX,
    window_seconds=settings.RATE_LIMIT_SUMMARIZE_WINDOW_SECONDS,
    endpoint_name="summarize",
)

#: General API limiter applied to all other endpoints.
global_limiter = SlidingWindowRateLimiter(
    max_requests=settings.RATE_LIMIT_GLOBAL_MAX,
    window_seconds=settings.RATE_LIMIT_GLOBAL_WINDOW_SECONDS,
    endpoint_name="api",
)


def get_request_key(request_obj) -> str:
    """Derive a rate-limit key from an incoming FastAPI Request.

    Prefers X-Forwarded-For (for proxied deployments) over direct client host.
    Returns 'unknown' if neither is resolvable, ensuring the limiter always
    operates rather than silently skipping.
    """
    forwarded_for = request_obj.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Use only the first (client) IP from the chain
        return forwarded_for.split(",")[0].strip()
    client = getattr(request_obj, "client", None)
    if client and client.host:
        return client.host
    return "unknown"
