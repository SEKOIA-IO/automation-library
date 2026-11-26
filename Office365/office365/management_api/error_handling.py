import json
import time
from collections.abc import Hashable
from typing import Any

from .constants import MAX_ERROR_BODY_LENGTH


class FailureTracker:
    """Track consecutive failures with deduplicated logging.

    Suppresses log spam during sustained outages while still surfacing:
    - the first few failures (so the issue is visible),
    - periodic markers (so dashboards see it's ongoing),
    - escalating level (warning -> error -> critical).

    A "signature" identifies the kind of failure (e.g. status code) so a
    different failure resets the streak even if it falls in the same category.
    """

    def __init__(self) -> None:
        self.consecutive: int = 0
        self.last_signature: Hashable | None = None
        self.first_failure_time: float | None = None

    def record(self, signature: Hashable) -> int:
        if signature == self.last_signature:
            self.consecutive += 1
        else:
            self.consecutive = 1
            self.last_signature = signature
            self.first_failure_time = time.time()
        return self.consecutive

    def reset(self) -> int:
        previous = self.consecutive
        self.consecutive = 0
        self.last_signature = None
        self.first_failure_time = None
        return previous

    def should_log(self) -> bool:
        n = self.consecutive
        if n <= 3:
            return True
        if n < 100:
            return n % 10 == 0
        return n % 100 == 0

    @property
    def log_level(self) -> str:
        n = self.consecutive
        if n <= 5:
            return "warning"
        if n <= 50:
            return "error"
        return "critical"

    @property
    def duration_seconds(self) -> float:
        if self.first_failure_time is None:
            return 0.0
        return time.time() - self.first_failure_time


def extract_error_metadata(
    body: str,
    status_code: int | None = None,
    max_body_length: int = MAX_ERROR_BODY_LENGTH,
) -> dict[str, Any]:
    """Build a context dict for an O365 exception from a response body.

    If the body is JSON with a top-level ``error`` object, extract ``code`` and
    ``message`` (truncated). Otherwise truncate the raw body. Avoids storing
    multi-KB HTML pages on the exception, which would otherwise be stringified
    into the logs.
    """
    context: dict[str, Any] = {}
    if status_code is not None:
        context["status_code"] = status_code

    body = body or ""

    try:
        parsed = json.loads(body)
    except (ValueError, TypeError):
        parsed = None

    if isinstance(parsed, dict):
        error = parsed.get("error")
        if isinstance(error, dict):
            code = error.get("code")
            message = error.get("message")
            if code:
                context["error_code"] = code
            if message:
                context["error_message"] = _truncate(str(message), max_body_length)
            if "error_code" in context or "error_message" in context:
                return context

    context["body"] = _truncate(body, max_body_length)
    return context


def _truncate(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return value[:max_length] + "...(truncated)"
