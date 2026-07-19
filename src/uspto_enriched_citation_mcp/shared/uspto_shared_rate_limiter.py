"""Shared USPTO API rate limiter, arbitrated across processes via POSIX file locks.

Context: multiple USPTO MCP containers (citations/pfw/ptab/fpd) can share one
host/netns under a SINGLE USPTO API key. USPTO's documented limits are
per-KEY, not per-process: burst=1 (no parallel requests), a handful of
req/sec by call type, and weekly quotas. A per-process semaphore/limiter
cannot see the other processes, so it cannot actually enforce a per-key
limit. This module coordinates a token bucket (rate) and a bounded pool of
concurrency slots (burst) across processes via a bind-mounted directory,
using flock — which the kernel releases automatically on process death, so
the scheme is crash-safe by construction.

Disabled by default: instantiated only when USPTO_SHARED_RATE_LIMIT_DIR is
set. This module is intentionally dependency-free (stdlib only, no imports
from any fpd_mcp package) so it can be vendored byte-identically into the
other USPTO MCP repos.

Env (read at construction):
    USPTO_SHARED_RATE_LIMIT_DIR   - enables the limiter iff set; directory
                                     for lock/state files (created if missing)
    USPTO_SHARED_RATE_LIMIT_RPS   - total tokens/sec across ALL processes
                                     (float, default 4.0)
    USPTO_SHARED_MAX_CONCURRENT   - shared in-flight slots (int, default 2)
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import logging
import os
import random
import time
from pathlib import Path
from typing import IO, Optional

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows
    # POSIX-only by design (the limiter runs in Linux containers). The
    # module must still IMPORT cleanly on Windows — the client imports
    # get_shared_limiter unconditionally, and STDIO dev runs on Windows.
    fcntl = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

_WAIT_WARN_SECONDS = 5.0
_POLL_MIN_SECONDS = 0.05
_POLL_MAX_SECONDS = 0.1


class SharedUsptoRateLimiter:
    """Cross-process token bucket + concurrency-slot limiter over a shared directory."""

    def __init__(self, directory: str) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

        self.rps = float(os.environ.get("USPTO_SHARED_RATE_LIMIT_RPS", "4.0"))
        self.max_concurrent = int(os.environ.get("USPTO_SHARED_MAX_CONCURRENT", "2"))
        self.capacity = max(self.rps * 2, 2.0)

        self._token_lock_path = self.directory / "token_bucket.lock"
        self._token_state_path = self.directory / "token_bucket.json"
        self._slot_paths = [
            self.directory / f"slot_{i}.lock" for i in range(self.max_concurrent)
        ]
        # Per-call-chain storage for the slot file handle acquired in
        # __aenter__ — a ContextVar (not `self.<attr>`) because one shared
        # limiter instance is entered concurrently by many in-flight
        # requests, each of which must release only the slot IT acquired.
        self._held_slot: contextvars.ContextVar[Optional[IO]] = contextvars.ContextVar(
            "uspto_shared_rate_limiter_held_slot", default=None
        )

        logger.info(
            "Shared USPTO rate limiter enabled: dir=%s rps=%.2f max_concurrent=%d",
            self.directory, self.rps, self.max_concurrent,
        )

    async def __aenter__(self) -> "SharedUsptoRateLimiter":
        await self._acquire_token()
        slot_fh = await self._acquire_slot()
        self._held_slot.set(slot_fh)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        slot_fh = self._held_slot.get()
        if slot_fh is not None:
            await asyncio.to_thread(self._release_slot, slot_fh)
            self._held_slot.set(None)

    # -- token bucket ------------------------------------------------------

    async def _acquire_token(self) -> None:
        start = time.monotonic()
        warned = False
        while True:
            if await asyncio.to_thread(self._try_take_token):
                return
            if not warned and (time.monotonic() - start) > _WAIT_WARN_SECONDS:
                logger.warning("Shared USPTO rate limiter: token acquire waiting > 5s")
                warned = True
            await asyncio.sleep(random.uniform(_POLL_MIN_SECONDS, _POLL_MAX_SECONDS))

    def _try_take_token(self) -> bool:
        with open(self._token_lock_path, "a+") as lockf:
            fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
            try:
                state = self._read_token_state()
                now = time.time()
                elapsed = max(0.0, now - state["last_refill"])
                tokens = min(self.capacity, state["tokens"] + elapsed * self.rps)
                if tokens >= 1.0:
                    self._write_token_state({"tokens": tokens - 1.0, "last_refill": now})
                    return True
                return False
            finally:
                fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)

    def _read_token_state(self) -> dict:
        try:
            with open(self._token_state_path, "r") as f:
                data = json.load(f)
            return {
                "tokens": float(data["tokens"]),
                "last_refill": float(data["last_refill"]),
            }
        except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError, TypeError):
            # Missing/corrupt state — reinitialize full rather than crash.
            return {"tokens": self.capacity, "last_refill": time.time()}

    def _write_token_state(self, state: dict) -> None:
        tmp_path = self._token_state_path.with_suffix(".tmp")
        with open(tmp_path, "w") as f:
            json.dump(state, f)
        os.replace(tmp_path, self._token_state_path)

    # -- concurrency slots --------------------------------------------------

    async def _acquire_slot(self) -> IO:
        start = time.monotonic()
        warned = False
        while True:
            slot_fh = await asyncio.to_thread(self._try_acquire_any_slot)
            if slot_fh is not None:
                return slot_fh
            if not warned and (time.monotonic() - start) > _WAIT_WARN_SECONDS:
                logger.warning("Shared USPTO rate limiter: concurrency slot wait > 5s")
                warned = True
            await asyncio.sleep(random.uniform(_POLL_MIN_SECONDS, _POLL_MAX_SECONDS))

    def _try_acquire_any_slot(self) -> Optional[IO]:
        for path in self._slot_paths:
            fh = open(path, "a+")
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return fh  # holding the lock; released in _release_slot
            except BlockingIOError:
                fh.close()
        return None

    def _release_slot(self, fh: IO) -> None:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        finally:
            fh.close()


_singleton: Optional[SharedUsptoRateLimiter] = None
_singleton_checked = False


def get_shared_limiter() -> Optional[SharedUsptoRateLimiter]:
    """Lazily construct and return the process-wide shared limiter singleton.

    Returns None (and never constructs anything) when
    USPTO_SHARED_RATE_LIMIT_DIR is unset — the disabled-by-default path.
    """
    global _singleton, _singleton_checked
    if not _singleton_checked:
        rate_limit_dir = os.environ.get("USPTO_SHARED_RATE_LIMIT_DIR")
        if rate_limit_dir:
            if fcntl is None:
                logger.warning(
                    "USPTO_SHARED_RATE_LIMIT_DIR is set but this platform has "
                    "no fcntl (Windows?) — shared rate limiting disabled. The "
                    "limiter is designed for the Linux container deployment."
                )
            else:
                _singleton = SharedUsptoRateLimiter(rate_limit_dir)
        _singleton_checked = True
    return _singleton
