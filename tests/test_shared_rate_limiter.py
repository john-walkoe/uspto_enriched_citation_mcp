"""Tests for shared/uspto_shared_rate_limiter.py (Item 2, shared USPTO rate
limiter; extended 2026-10-13 for the ODP rate-limit wave, plan 4c.1).

Ported from the canonical copy's tests in uspto_ptab_mcp
(tests/test_shared_rate_limiter.py) with this package's import path; the
module itself is vendored byte-for-byte from there (md5 pinned in
test_vendored_module_hashes.py).

Covers: disabled-by-default, single-process token bucket deplete/refill,
single-process concurrency-slot serialization, corrupt-state recovery, and
the wave's rules: two real processes on one directory never overlap in
flight; consecutive sends are >= 1/RPS apart; FIFO order across processes;
a cooldown written by one process is honoured by another; TimeoutError at
the wait ceiling; an old-format token_bucket.json is read correctly (mixed
rollout); a crashed head ticket does not wedge the queue.
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

import uspto_enriched_citation_mcp.shared.uspto_shared_rate_limiter as rate_limiter_module
from uspto_enriched_citation_mcp.shared.uspto_shared_rate_limiter import (
    SharedLimiterTimeoutError,
    SharedUsptoRateLimiter,
)

_SRC_PATH = Path(__file__).parent.parent / "src"


@pytest.fixture(autouse=True)
def _isolated_singleton(monkeypatch):
    """Reset the module-level lazy singleton and env vars around every test
    in this file so tests never see another test's (or another module's)
    cached limiter."""
    monkeypatch.setattr(rate_limiter_module, "_singleton", None)
    monkeypatch.setattr(rate_limiter_module, "_singleton_checked", False)
    monkeypatch.delenv("USPTO_SHARED_RATE_LIMIT_DIR", raising=False)
    monkeypatch.delenv("USPTO_SHARED_RATE_LIMIT_RPS", raising=False)
    monkeypatch.delenv("USPTO_SHARED_MAX_CONCURRENT", raising=False)
    monkeypatch.delenv("USPTO_SHARED_MAX_WAIT_SECONDS", raising=False)
    yield


def test_disabled_by_default():
    assert rate_limiter_module.get_shared_limiter() is None


def test_note_429_is_a_no_op_when_disabled(tmp_path):
    rate_limiter_module.note_429(7.0)  # must not raise or create anything
    assert rate_limiter_module.get_shared_limiter() is None


def test_enabled_when_dir_env_set_and_is_singleton(tmp_path, monkeypatch):
    monkeypatch.setenv("USPTO_SHARED_RATE_LIMIT_DIR", str(tmp_path))

    limiter1 = rate_limiter_module.get_shared_limiter()
    limiter2 = rate_limiter_module.get_shared_limiter()

    assert limiter1 is not None
    assert limiter1 is limiter2  # lazy singleton, not re-constructed


def test_defaults_match_the_published_limits(tmp_path):
    """Burst 1 per key, 45 s wait ceiling, capacity-1 bucket (plan 2b)."""
    limiter = SharedUsptoRateLimiter(str(tmp_path))
    assert limiter.max_concurrent == 1
    assert limiter.max_wait_seconds == 45.0
    assert limiter.capacity == 1.0
    assert limiter.rps == 4.0


@pytest.mark.asyncio
async def test_token_bucket_depletes_and_refills(tmp_path, monkeypatch):
    monkeypatch.setenv("USPTO_SHARED_RATE_LIMIT_RPS", "50")
    monkeypatch.setenv("USPTO_SHARED_MAX_CONCURRENT", "10")
    limiter = SharedUsptoRateLimiter(str(tmp_path))

    # Empty bucket right now -> next acquire must wait for a partial refill
    # (~1/rps = 0.02s at rps=50), not be instantaneous.
    limiter._write_token_state({"tokens": 0.0, "last_refill": time.time()})
    start = time.monotonic()
    async with limiter:
        pass
    elapsed = time.monotonic() - start
    assert elapsed >= 0.01
    assert elapsed < 2.0

    # A bucket with a token available is taken immediately (no poll-sleep).
    limiter._write_token_state({"tokens": 1.0, "last_refill": time.time()})
    start2 = time.monotonic()
    async with limiter:
        pass
    elapsed2 = time.monotonic() - start2
    assert elapsed2 < 0.05


def test_old_format_token_bucket_json_is_read_correctly(tmp_path, monkeypatch):
    """Mixed rollout: the previous limiter banked up to rps*2 tokens in the
    same file. The new one reads that file as is, clamps the balance to its
    capacity of 1.0, and writes the same two keys back, so an old process
    beside a new one keeps reading a file it understands."""
    monkeypatch.setenv("USPTO_SHARED_RATE_LIMIT_RPS", "4")
    limiter = SharedUsptoRateLimiter(str(tmp_path))
    state_path = tmp_path / "token_bucket.json"

    now = time.time()
    state_path.write_text(json.dumps({"tokens": 8.0, "last_refill": now}))  # old capacity 8
    assert limiter._try_take_token() is True
    written = json.loads(state_path.read_text())
    assert set(written) == {"tokens", "last_refill"}
    assert written["tokens"] == pytest.approx(0.0, abs=0.01)  # clamped to 1.0, minus the take

    # An old-format file with an EMPTY bucket refilled 0.25 s ago at 4 rps
    # holds exactly one token; one with no refill time elapsed holds none.
    state_path.write_text(json.dumps({"tokens": 0.0, "last_refill": time.time() - 0.3}))
    assert limiter._try_take_token() is True
    state_path.write_text(json.dumps({"tokens": 0.0, "last_refill": time.time()}))
    assert limiter._try_take_token() is False


@pytest.mark.asyncio
async def test_concurrency_slot_serializes_two_tasks(tmp_path, monkeypatch):
    monkeypatch.setenv("USPTO_SHARED_RATE_LIMIT_RPS", "1000")  # tokens aren't the bottleneck
    monkeypatch.setenv("USPTO_SHARED_MAX_CONCURRENT", "1")
    limiter = SharedUsptoRateLimiter(str(tmp_path))

    intervals = []

    async def worker():
        async with limiter:
            start = time.monotonic()
            await asyncio.sleep(0.1)
            end = time.monotonic()
            intervals.append((start, end))

    await asyncio.gather(worker(), worker())

    assert len(intervals) == 2
    (s1, e1), (s2, e2) = intervals
    # Strictly serialized: one interval must fully end before the other starts.
    assert e1 <= s2 or e2 <= s1


def test_corrupt_state_file_recovers(tmp_path, monkeypatch):
    monkeypatch.setenv("USPTO_SHARED_RATE_LIMIT_RPS", "50")
    monkeypatch.setenv("USPTO_SHARED_MAX_CONCURRENT", "2")
    limiter = SharedUsptoRateLimiter(str(tmp_path))

    state_path = tmp_path / "token_bucket.json"
    state_path.write_text("{not valid json at all")

    got = limiter._try_take_token()
    assert got is True  # reinitialized to a full bucket rather than raising

    with open(state_path) as f:
        data = json.load(f)
    assert data["tokens"] == pytest.approx(limiter.capacity - 1.0)


def test_missing_state_file_recovers(tmp_path, monkeypatch):
    monkeypatch.setenv("USPTO_SHARED_RATE_LIMIT_RPS", "50")
    monkeypatch.setenv("USPTO_SHARED_MAX_CONCURRENT", "2")
    limiter = SharedUsptoRateLimiter(str(tmp_path))

    assert not (tmp_path / "token_bucket.json").exists()
    got = limiter._try_take_token()
    assert got is True


def test_corrupt_queue_files_recover(tmp_path):
    limiter = SharedUsptoRateLimiter(str(tmp_path))
    (tmp_path / "queue_ticket.json").write_text("nope")
    (tmp_path / "queue_serving.json").write_text("[1, 2]")
    (tmp_path / "cooldown.json").write_text("{\"cooldown_until\": \"soon\"}")

    assert limiter._read_serving() == (0, 0.0)
    assert limiter._read_cooldown_until() == 0.0
    assert limiter._take_ticket() == 0
    assert limiter._read_serving()[0] == 0  # the new head, heartbeat started


# ---------------------------------------------------------------- cooldown

def test_note_429_writes_the_floor_and_never_shortens(tmp_path, monkeypatch):
    monkeypatch.setenv("USPTO_SHARED_RATE_LIMIT_DIR", str(tmp_path))
    limiter = rate_limiter_module.get_shared_limiter()
    before = time.time()

    rate_limiter_module.note_429(None)  # the module function routes to the singleton
    until = limiter._read_cooldown_until()
    assert until >= before + 5.0  # USPTO's published floor
    assert until <= time.time() + 5.0 + 0.5

    limiter.note_429(30)
    assert limiter._read_cooldown_until() >= before + 30.0

    limiter.note_429(2)  # a shorter Retry-After never shortens an active cooldown
    assert limiter._read_cooldown_until() >= before + 30.0


@pytest.mark.asyncio
async def test_an_active_cooldown_is_waited_out_before_the_slot(tmp_path, monkeypatch):
    monkeypatch.setenv("USPTO_SHARED_RATE_LIMIT_RPS", "1000")
    limiter = SharedUsptoRateLimiter(str(tmp_path))
    (tmp_path / "cooldown.json").write_text(json.dumps({"cooldown_until": time.time() + 0.3}))

    start = time.monotonic()
    async with limiter:
        waited = time.monotonic() - start
    assert waited >= 0.25
    assert limiter.last_wait_seconds >= 0.25


@pytest.mark.asyncio
async def test_timeout_error_at_the_ceiling_releases_nothing_it_did_not_take(tmp_path, monkeypatch):
    """A second instance on the same directory (its own flock handle, so it
    contends like another process) gives up at the ceiling with a
    TimeoutError the caller can answer with the rate-limit envelope."""
    monkeypatch.setenv("USPTO_SHARED_RATE_LIMIT_RPS", "1000")
    holder = SharedUsptoRateLimiter(str(tmp_path))
    monkeypatch.setenv("USPTO_SHARED_MAX_WAIT_SECONDS", "0.3")
    waiter = SharedUsptoRateLimiter(str(tmp_path))
    assert waiter.max_wait_seconds == 0.3

    async with holder:
        start = time.monotonic()
        with pytest.raises(SharedLimiterTimeoutError, match="request slot"):
            async with waiter:
                pass
        assert 0.3 <= time.monotonic() - start < 2.0
        assert isinstance(SharedLimiterTimeoutError("x"), TimeoutError)
        # The waiter abandoned its head ticket, so the next ticket is served.
        assert waiter._read_serving()[0] == waiter.last_ticket + 1

    # And the holder's slot is back once it exits.
    async with waiter:
        pass


@pytest.mark.asyncio
async def test_a_crashed_head_ticket_does_not_wedge_the_queue(tmp_path, monkeypatch):
    """A waiter that took a ticket and died never advances `serving`. The
    staleness rule (no heartbeat for head_stale_seconds) skips it."""
    monkeypatch.setenv("USPTO_SHARED_RATE_LIMIT_RPS", "1000")
    limiter = SharedUsptoRateLimiter(str(tmp_path))
    limiter.head_stale_seconds = 0.3

    dead_ticket = limiter._take_ticket()  # ticket 0, never served, never heartbeats
    assert dead_ticket == 0

    start = time.monotonic()
    async with limiter:
        waited = time.monotonic() - start
    assert limiter.last_ticket == 1
    assert 0.3 <= waited < 2.0


# ---------------------------------------------------------------- cross-process

_WORKER_SCRIPT = """
import asyncio, json, sys, time
sys.path.insert(0, {src_path!r})
import uspto_enriched_citation_mcp.shared.uspto_shared_rate_limiter as srl
from uspto_enriched_citation_mcp.shared.uspto_shared_rate_limiter import SharedUsptoRateLimiter

async def main():
    limiter = SharedUsptoRateLimiter({directory!r})
    await asyncio.sleep({start_delay!r})
    if {cooldown_floor!r} is not None:
        srl._COOLDOWN_FLOOR_SECONDS = {cooldown_floor!r}
        limiter.note_429(None)
        with open({out_file!r}, "w") as f:
            json.dump({{"noted_at": time.time()}}, f)
        return
    sends = []
    for _ in range({sends!r}):
        async with limiter:
            start = time.time()
            await asyncio.sleep({hold!r})
            end = time.time()
        sends.append({{"ticket": limiter.last_ticket, "start": start, "end": end}})
    with open({out_file!r}, "w") as f:
        json.dump(sends, f)

asyncio.run(main())
"""


def _spawn(directory, out_file, rps, sends=1, hold=0.0, start_delay=0.0, cooldown_floor=None,
           max_wait="45"):
    script = _WORKER_SCRIPT.format(
        src_path=str(_SRC_PATH), directory=str(directory), out_file=str(out_file),
        sends=sends, hold=hold, start_delay=start_delay, cooldown_floor=cooldown_floor,
    )
    return subprocess.Popen(
        [sys.executable, "-c", script],
        env={
            **os.environ,
            "USPTO_SHARED_RATE_LIMIT_RPS": str(rps),
            "USPTO_SHARED_MAX_CONCURRENT": "1",
            "USPTO_SHARED_MAX_WAIT_SECONDS": max_wait,
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _finish(procs):
    for proc in procs:
        out, err = proc.communicate(timeout=60)
        assert proc.returncode == 0, err.decode()


def _load(out_file):
    with open(out_file) as f:
        return json.load(f)


def test_cross_process_two_workers_never_overlap_in_flight(tmp_path):
    """Two independent `python -c` processes share a rate-limit directory
    with max_concurrent=1: the flock-based slot must serialize them even
    though they don't share any Python-level state."""
    directory = tmp_path / "shared"
    out_files = [tmp_path / "worker0.json", tmp_path / "worker1.json"]
    procs = [_spawn(directory, out, rps=1000, sends=2, hold=0.15) for out in out_files]
    _finish(procs)

    intervals = sorted(
        (send["start"], send["end"]) for out in out_files for send in _load(out)
    )
    assert len(intervals) == 4
    for (_, end_a), (start_b, _) in zip(intervals, intervals[1:]):
        assert end_a <= start_b


def test_cross_process_consecutive_sends_are_at_least_one_over_rps_apart(tmp_path):
    """Capacity 1.0 and slot-then-token ordering: across two processes the
    sends are spaced >= 1/RPS even with no hold time at all."""
    rps = 10
    directory = tmp_path / "shared"
    out_files = [tmp_path / "worker0.json", tmp_path / "worker1.json"]
    procs = [_spawn(directory, out, rps=rps, sends=3, hold=0.0) for out in out_files]
    _finish(procs)

    starts = sorted(send["start"] for out in out_files for send in _load(out))
    assert len(starts) == 6
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    assert min(gaps) >= (1.0 / rps) - 0.005, gaps


def test_cross_process_fifo_order(tmp_path):
    """Three processes: the first holds the slot while the other two arrive
    in a known order; they must be served in that order (ticket order), not
    whichever polled first when the slot freed."""
    directory = tmp_path / "shared"
    outs = [tmp_path / f"worker{i}.json" for i in range(3)]
    procs = [
        _spawn(directory, outs[0], rps=1000, sends=1, hold=1.2, start_delay=0.0),
        _spawn(directory, outs[1], rps=1000, sends=1, hold=0.05, start_delay=0.4),
        _spawn(directory, outs[2], rps=1000, sends=1, hold=0.05, start_delay=0.8),
    ]
    _finish(procs)

    sends = [_load(out)[0] for out in outs]
    assert [s["ticket"] for s in sends] == [0, 1, 2]
    assert sends[0]["end"] <= sends[1]["start"] <= sends[1]["end"] <= sends[2]["start"]


def test_cross_process_cooldown_written_by_one_is_honoured_by_another(tmp_path):
    """Process A notes a 429 (its floor patched down to 0.6 s so the test
    stays fast); process B, unpatched, must not take a slot before the
    cooldown A wrote has passed."""
    directory = tmp_path / "shared"
    noted = tmp_path / "noted.json"
    sent = tmp_path / "sent.json"
    procs = [
        _spawn(directory, noted, rps=1000, cooldown_floor=0.6),
        _spawn(directory, sent, rps=1000, sends=1, hold=0.0, start_delay=0.3),
    ]
    _finish(procs)

    noted_at = _load(noted)["noted_at"]
    start = _load(sent)[0]["start"]
    assert start >= noted_at + 0.6 - 0.01
