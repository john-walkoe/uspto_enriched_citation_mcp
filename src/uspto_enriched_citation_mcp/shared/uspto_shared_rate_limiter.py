"""Shared USPTO API rate limiter, arbitrated across processes via POSIX file locks.

Context: multiple USPTO MCP containers (citations/pfw/ptab/fpd) can share one
host/netns under a SINGLE USPTO API key. USPTO's documented limits are
per-KEY, not per-process: burst=1 (no parallel requests), a handful of
req/sec by call type, weekly quotas, and no retry within 5 s of a 429. A
per-process semaphore/limiter cannot see the other processes, so it cannot
actually enforce a per-key limit. This module coordinates, across processes
sharing a bind-mounted directory:

  1. a FIFO queue (ticket counter + "next to serve" value), so waiters are
     served in arrival order instead of poll-and-grab, which starves one
     server under load;
  2. a bounded pool of concurrency slots (burst), one flock file per slot,
     which the kernel releases automatically on process death;
  3. a token bucket (rate) with capacity 1.0 (no banked tokens), taken AFTER
     the slot, so two consecutive sends on the key are always >= 1/RPS apart;
  4. a shared 429 cooldown: one 429 on the key means the key is hot for every
     process, so every acquire waits the cooldown out before taking a slot.

Acquire order is: take a ticket -> wait until it is the head of the queue ->
wait out any cooldown -> take a slot -> advance the queue -> take a token ->
send. The slot is released by the context manager's exit.

Files in the directory (names and formats are stable so that an OLD process
running the previous version of this module beside a NEW one still
interoperates: both take the same slot_N.lock files and read/write the same
token_bucket.json; the old process simply never takes a ticket):
    token_bucket.lock / token_bucket.json   {"tokens": float, "last_refill": epoch}
    slot_<n>.lock                           flock per concurrency slot
    queue_ticket.lock                       guards the three queue files below
    queue_ticket.json                       {"next_ticket": int}
    queue_serving.json                      {"serving": int, "since": epoch}
    cooldown.json                           {"cooldown_until": epoch}

Crashed waiters. flock covers a crashed HOLDER (the kernel drops the lock),
but a waiter that dies holding the head ticket would wedge the queue, because
only the head advances `serving`. So the head heartbeats `since` on every
poll while it waits, and any later waiter that sees the head ticket un-
advanced for more than `_HEAD_STALE_SECONDS` (2 s, far above the poll
interval) advances `serving` past it. A live head that was merely suspended
that long still gets served: a waiter whose ticket is already BELOW `serving`
just takes a slot directly (the slots are flocks, so safety never depends on
the queue; only fairness does).

Disabled by default: instantiated only when USPTO_SHARED_RATE_LIMIT_DIR is
set. This module is intentionally dependency-free (stdlib only, no imports
from any ptab_mcp/fpd_mcp/pfw package) so it can be vendored byte-identically
into the other USPTO MCP repos. It must IMPORT on Windows (fcntl is None
there and the limiter reports itself disabled).

Env (read at construction):
    USPTO_SHARED_RATE_LIMIT_DIR    - enables the limiter iff set; directory
                                      for lock/state files (created if missing)
    USPTO_SHARED_RATE_LIMIT_RPS    - total tokens/sec across ALL processes
                                      (float, default 4.0)
    USPTO_SHARED_MAX_CONCURRENT    - shared in-flight slots (int, default 1,
                                      USPTO's published burst limit per key)
    USPTO_SHARED_MAX_WAIT_SECONDS  - ceiling on one acquire, queue wait
                                      included (float, default 45); past it
                                      SharedLimiterTimeoutError (a TimeoutError)
                                      is raised and the caller answers with
                                      its rate-limit envelope

Measurement: `last_wait_seconds` on the instance is the queue wait of the most
recent acquire (callers that count waits read it); an acquire whose wait or
whose slot hold exceeds 5 s is logged at INFO, never per call.
"""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import json
import logging
import os
import random
import time
from pathlib import Path
from typing import IO, Optional, Tuple

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows
    # POSIX-only by design (the limiter runs in Linux containers). The
    # module must still IMPORT cleanly on Windows: the client imports
    # get_shared_limiter unconditionally, and STDIO dev runs on Windows.
    fcntl = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

#: Queue wait or slot hold above this is logged (INFO), once per acquire.
_WAIT_LOG_SECONDS = 5.0
#: Default ceiling on one acquire (queue wait included), overridable per
#: process with USPTO_SHARED_MAX_WAIT_SECONDS. 45 s sits under the roughly
#: 100 s Cloudflare cut in front of the hosted servers and under FPD's 85 s
#: call deadlines, so a refusal still reaches the caller as a structured
#: envelope instead of a dropped connection.
_DEFAULT_MAX_WAIT_SECONDS = 45.0
#: Floor on the shared 429 cooldown: USPTO's own published "no retry within
#: 5 s" rule. A Retry-After header above it lengthens the cooldown; nothing
#: shortens it.
_COOLDOWN_FLOOR_SECONDS = 5.0
#: A head ticket whose heartbeat is older than this is presumed dead and
#: skipped. The poll interval is 0.05 to 0.1 s, so a live head refreshes the
#: heartbeat 20 to 40 times inside this window.
_HEAD_STALE_SECONDS = 2.0
_POLL_MIN_SECONDS = 0.05
_POLL_MAX_SECONDS = 0.1


class SharedLimiterTimeoutError(TimeoutError):
    """Raised when an acquire exceeds the wait ceiling. A TimeoutError so
    existing `except TimeoutError` handlers keep working; a subclass so a
    caller can tell the shared limiter's refusal from any other timeout."""


def _max_wait_seconds_from_env() -> float:
    raw = os.environ.get("USPTO_SHARED_MAX_WAIT_SECONDS", "")
    try:
        value = float(raw) if raw else _DEFAULT_MAX_WAIT_SECONDS
    except ValueError:
        value = _DEFAULT_MAX_WAIT_SECONDS
    return value if value > 0 else _DEFAULT_MAX_WAIT_SECONDS


def _write_json_atomic(path: Path, payload: dict) -> None:
    tmp_path = path.with_name(path.name + ".tmp")
    with open(tmp_path, "w") as f:
        json.dump(payload, f)
    os.replace(tmp_path, path)


def _read_json(path: Path) -> Optional[dict]:
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, ValueError, OSError):
        return None
    return data if isinstance(data, dict) else None


class SharedUsptoRateLimiter:
    """Cross-process FIFO queue + concurrency slots + token bucket + 429
    cooldown over a shared directory. Use as an async context manager around
    exactly one outbound USPTO send."""

    def __init__(self, directory: str) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

        self.rps = float(os.environ.get("USPTO_SHARED_RATE_LIMIT_RPS", "4.0"))
        self.max_concurrent = int(os.environ.get("USPTO_SHARED_MAX_CONCURRENT", "1"))
        # Capacity 1.0: no banked tokens, so a burst after an idle period is
        # still paced at 1/RPS. An old-format token_bucket.json written by a
        # previous version (capacity rps*2) is read fine; its token count is
        # simply clamped to 1.0 on the next refill.
        self.capacity = 1.0
        self.max_wait_seconds = _max_wait_seconds_from_env()
        self.head_stale_seconds = _HEAD_STALE_SECONDS

        self._token_lock_path = self.directory / "token_bucket.lock"
        self._token_state_path = self.directory / "token_bucket.json"
        self._slot_paths = [
            self.directory / f"slot_{i}.lock" for i in range(self.max_concurrent)
        ]
        self._queue_lock_path = self.directory / "queue_ticket.lock"
        self._ticket_path = self.directory / "queue_ticket.json"
        self._serving_path = self.directory / "queue_serving.json"
        self._cooldown_path = self.directory / "cooldown.json"

        # Per-call-chain storage for (slot file handle, acquire time) taken in
        # __aenter__: a ContextVar (not `self.<attr>`) because one shared
        # limiter instance is entered concurrently by many in-flight
        # requests, each of which must release only the slot IT acquired.
        self._held_slot: contextvars.ContextVar[Optional[Tuple[IO, float]]] = (
            contextvars.ContextVar("uspto_shared_rate_limiter_held_slot", default=None)
        )
        #: Queue wait (ticket taken -> token taken) of the most recent acquire
        #: in this process, in seconds. Best-effort measurement, not state.
        self.last_wait_seconds: float = 0.0
        #: Ticket of the most recent acquire in this process (measurement).
        self.last_ticket: int = -1

        logger.info(
            "Shared USPTO rate limiter enabled: dir=%s rps=%.2f max_concurrent=%d "
            "max_wait=%.0fs",
            self.directory, self.rps, self.max_concurrent, self.max_wait_seconds,
        )

    # -- context manager ----------------------------------------------------

    async def __aenter__(self) -> "SharedUsptoRateLimiter":
        started = time.monotonic()
        deadline = started + self.max_wait_seconds
        ticket = await asyncio.to_thread(self._take_ticket)
        self.last_ticket = ticket
        slot_fh: Optional[IO] = None
        try:
            slot_fh = await self._acquire_slot_fifo(ticket, deadline)
            await self._acquire_token(deadline)
        except BaseException:
            if slot_fh is not None:
                await asyncio.to_thread(self._release_slot, slot_fh)
            else:
                await asyncio.to_thread(self._abandon_ticket, ticket)
            raise
        finally:
            self.last_wait_seconds = time.monotonic() - started
        if self.last_wait_seconds > _WAIT_LOG_SECONDS:
            logger.info(
                "Shared USPTO rate limiter: queue wait %.1fs (ticket %d)",
                self.last_wait_seconds, ticket,
            )
        self._held_slot.set((slot_fh, time.monotonic()))
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        held = self._held_slot.get()
        if held is not None:
            slot_fh, acquired_at = held
            self._held_slot.set(None)
            await asyncio.to_thread(self._release_slot, slot_fh)
            hold = time.monotonic() - acquired_at
            if hold > _WAIT_LOG_SECONDS:
                logger.info("Shared USPTO rate limiter: slot held %.1fs", hold)

    # -- 429 cooldown -------------------------------------------------------

    def note_429(self, retry_after: Optional[float]) -> None:
        """Record a 429 seen on the key: every acquire in every process on
        this directory waits until now + max(5 s, retry_after) before taking
        a slot. An existing longer cooldown is never shortened."""
        try:
            wait = max(_COOLDOWN_FLOOR_SECONDS, float(retry_after or 0.0))
        except (TypeError, ValueError):
            wait = _COOLDOWN_FLOOR_SECONDS
        until = time.time() + wait
        current = self._read_cooldown_until()
        if until > current:
            _write_json_atomic(self._cooldown_path, {"cooldown_until": until})
        logger.warning(
            "Shared USPTO rate limiter: 429 on the key, cooldown %.0fs for every process",
            wait,
        )

    def _read_cooldown_until(self) -> float:
        data = _read_json(self._cooldown_path)
        if not data:
            return 0.0
        try:
            return float(data["cooldown_until"])
        except (KeyError, TypeError, ValueError):
            return 0.0

    # -- FIFO queue + concurrency slots ------------------------------------

    @contextlib.contextmanager
    def _locked(self, lock_path: Path):
        with open(lock_path, "a+") as lockf:
            fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)

    def _read_counter(self, path: Path, key: str) -> int:
        data = _read_json(path)
        if not data:
            return 0
        try:
            return max(0, int(data[key]))
        except (KeyError, TypeError, ValueError):
            return 0

    def _read_serving(self) -> Tuple[int, float]:
        data = _read_json(self._serving_path)
        if not data:
            return 0, 0.0
        try:
            return max(0, int(data["serving"])), float(data.get("since", 0.0))
        except (KeyError, TypeError, ValueError):
            return 0, 0.0

    def _write_serving(self, serving: int, since: float) -> None:
        _write_json_atomic(self._serving_path, {"serving": serving, "since": since})

    def _take_ticket(self) -> int:
        with self._locked(self._queue_lock_path):
            ticket = self._read_counter(self._ticket_path, "next_ticket")
            _write_json_atomic(self._ticket_path, {"next_ticket": ticket + 1})
            serving, _ = self._read_serving()
            if serving == ticket:
                # The queue was empty: this ticket is the head from now, so
                # its staleness clock starts at arrival (a fresh directory
                # has no `since` at all and would read as stale at once).
                self._write_serving(ticket, time.time())
            return ticket

    def _abandon_ticket(self, ticket: int) -> None:
        """A waiter that gives up (timeout, cancellation) while at the head
        of the queue hands the head to the next ticket at once rather than
        leaving the staleness rule to do it 2 s later."""
        with self._locked(self._queue_lock_path):
            serving, _ = self._read_serving()
            if serving == ticket:
                self._write_serving(ticket + 1, time.time())

    def _queue_step(self, ticket: int) -> Tuple[str, Optional[IO]]:
        """One poll of the queue for `ticket`. Returns (state, slot_fh):
        "acquired" with the slot handle; "queued" (not our turn yet);
        "cooldown" or "slot_busy" (our turn, but not yet sendable)."""
        with self._locked(self._queue_lock_path):
            now = time.time()
            serving, since = self._read_serving()
            if serving < ticket:
                if now - since > self.head_stale_seconds:
                    # The head stopped heartbeating: presumed dead, skipped.
                    self._write_serving(serving + 1, now)
                return "queued", None
            is_head = serving == ticket
            if self._read_cooldown_until() > now:
                if is_head:
                    self._write_serving(ticket, now)  # heartbeat
                return "cooldown", None
            slot_fh = self._try_acquire_any_slot()
            if slot_fh is None:
                if is_head:
                    self._write_serving(ticket, now)  # heartbeat
                return "slot_busy", None
            if is_head:
                self._write_serving(ticket + 1, now)
            return "acquired", slot_fh

    async def _acquire_slot_fifo(self, ticket: int, deadline: float) -> IO:
        while True:
            state, slot_fh = await asyncio.to_thread(self._queue_step, ticket)
            if slot_fh is not None:
                return slot_fh
            if time.monotonic() > deadline:
                raise SharedLimiterTimeoutError(
                    f"shared USPTO rate limiter: no request slot within "
                    f"{self.max_wait_seconds:.0f}s (ticket {ticket}, last state "
                    f"{state}); the key is busy or cooling down after a 429"
                )
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

    # -- token bucket ------------------------------------------------------

    async def _acquire_token(self, deadline: float) -> None:
        while True:
            if await asyncio.to_thread(self._try_take_token):
                return
            if time.monotonic() > deadline:
                raise SharedLimiterTimeoutError(
                    f"shared USPTO rate limiter: no rate token within "
                    f"{self.max_wait_seconds:.0f}s"
                )
            await asyncio.sleep(random.uniform(_POLL_MIN_SECONDS, _POLL_MAX_SECONDS))

    def _try_take_token(self) -> bool:
        with self._locked(self._token_lock_path):
            state = self._read_token_state()
            now = time.time()
            elapsed = max(0.0, now - state["last_refill"])
            tokens = min(self.capacity, state["tokens"] + elapsed * self.rps)
            if tokens >= 1.0:
                self._write_token_state({"tokens": tokens - 1.0, "last_refill": now})
                return True
            return False

    def _read_token_state(self) -> dict:
        try:
            with open(self._token_state_path, "r") as f:
                data = json.load(f)
            return {
                "tokens": float(data["tokens"]),
                "last_refill": float(data["last_refill"]),
            }
        except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError, TypeError):
            # Missing/corrupt state: reinitialize full rather than crash.
            return {"tokens": self.capacity, "last_refill": time.time()}

    def _write_token_state(self, state: dict) -> None:
        _write_json_atomic(self._token_state_path, state)


_singleton: Optional[SharedUsptoRateLimiter] = None
_singleton_checked = False


def get_shared_limiter() -> Optional[SharedUsptoRateLimiter]:
    """Lazily construct and return the process-wide shared limiter singleton.

    Returns None (and never constructs anything) when
    USPTO_SHARED_RATE_LIMIT_DIR is unset, the disabled-by-default path.
    """
    global _singleton, _singleton_checked
    if not _singleton_checked:
        rate_limit_dir = os.environ.get("USPTO_SHARED_RATE_LIMIT_DIR")
        if rate_limit_dir:
            if fcntl is None:
                logger.warning(
                    "USPTO_SHARED_RATE_LIMIT_DIR is set but this platform has "
                    "no fcntl (Windows?), so shared rate limiting is disabled. "
                    "The limiter is designed for the Linux container deployment."
                )
            else:
                _singleton = SharedUsptoRateLimiter(rate_limit_dir)
        _singleton_checked = True
    return _singleton


def note_429(retry_after: Optional[float]) -> None:
    """Record a 429 on the shared key (see SharedUsptoRateLimiter.note_429).
    A no-op when the limiter is disabled."""
    limiter = get_shared_limiter()
    if limiter is not None:
        limiter.note_429(retry_after)
