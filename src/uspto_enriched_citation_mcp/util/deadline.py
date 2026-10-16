"""One end-to-end time budget for a multi-request tool call.

Cloudflare cuts a proxied request at about 100 s, and claude.ai then sees an
error the server never hears about. Citations_get_citation_statistics fans
out six count queries (the base query plus five breakdowns), each with its
own HTTP timeout and retries. One Deadline is created when the tool starts;
the fan-out waits only for what is left of it, so retries and backoff stay
inside the one budget rather than each attempt getting a fresh one, and the
counts that did return in time are kept.

Env:
    CITATIONS_CONTENT_DEADLINE_SECONDS   budget per statistics call (default
                                         85, under the ~100 s cut)
"""

from __future__ import annotations

import os
import time
from typing import Callable

from .logging import get_logger

logger = get_logger(__name__)

DEFAULT_CONTENT_DEADLINE_SECONDS = 85.0


class Deadline:
    """A monotonic end time. `clock` is injectable so tests can fake time."""

    def __init__(self, seconds: float, clock: Callable[[], float] = time.monotonic) -> None:
        self.seconds = float(seconds)
        self._clock = clock
        self._end = clock() + self.seconds

    def remaining(self) -> float:
        """Seconds left, never negative."""
        return max(0.0, self._end - self._clock())

    def expired(self) -> bool:
        return self.remaining() <= 0.0


def content_deadline_seconds() -> float:
    """CITATIONS_CONTENT_DEADLINE_SECONDS, else 85; non-positive or junk -> 85."""
    raw = os.getenv("CITATIONS_CONTENT_DEADLINE_SECONDS", "").strip()
    if not raw:
        return DEFAULT_CONTENT_DEADLINE_SECONDS
    try:
        value = float(raw)
    except ValueError:
        logger.warning("Invalid CITATIONS_CONTENT_DEADLINE_SECONDS, using default 85")
        return DEFAULT_CONTENT_DEADLINE_SECONDS
    return value if value > 0 else DEFAULT_CONTENT_DEADLINE_SECONDS
