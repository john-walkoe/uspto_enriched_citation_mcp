"""Tests for shared/uspto_shared_rate_limiter.py (Item 2 — shared USPTO rate
limiter). Covers: disabled-by-default, single-process token bucket
deplete/refill, single-process concurrency-slot serialization, cross-process
serialization via real subprocesses sharing a directory, and corrupt-state
recovery.
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
from uspto_enriched_citation_mcp.shared.uspto_shared_rate_limiter import SharedUsptoRateLimiter

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
    yield


def test_disabled_by_default():
    assert rate_limiter_module.get_shared_limiter() is None


def test_enabled_when_dir_env_set_and_is_singleton(tmp_path, monkeypatch):
    monkeypatch.setenv("USPTO_SHARED_RATE_LIMIT_DIR", str(tmp_path))

    limiter1 = rate_limiter_module.get_shared_limiter()
    limiter2 = rate_limiter_module.get_shared_limiter()

    assert limiter1 is not None
    assert limiter1 is limiter2  # lazy singleton, not re-constructed


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

    # A bucket with tokens available is taken immediately (no poll-sleep).
    limiter._write_token_state({"tokens": 5.0, "last_refill": time.time()})
    start2 = time.monotonic()
    async with limiter:
        pass
    elapsed2 = time.monotonic() - start2
    assert elapsed2 < 0.05


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


_WORKER_SCRIPT = """
import asyncio, json, sys, time
sys.path.insert(0, {src_path!r})
from uspto_enriched_citation_mcp.shared.uspto_shared_rate_limiter import SharedUsptoRateLimiter

async def main():
    limiter = SharedUsptoRateLimiter({directory!r})
    async with limiter:
        start = time.time()
        await asyncio.sleep(0.3)
        end = time.time()
    with open({out_file!r}, "w") as f:
        json.dump({{"start": start, "end": end}}, f)

asyncio.run(main())
"""


def test_cross_process_concurrency_slot_serializes_two_workers(tmp_path, monkeypatch):
    """Two independent `python -c` processes share a rate-limit directory
    with max_concurrent=1 — the flock-based slot must serialize them even
    though they don't share any Python-level state."""
    monkeypatch.setenv("USPTO_SHARED_RATE_LIMIT_RPS", "1000")
    monkeypatch.setenv("USPTO_SHARED_MAX_CONCURRENT", "1")

    directory = tmp_path / "shared"
    out_files = [tmp_path / "worker0.json", tmp_path / "worker1.json"]

    procs = []
    for out_file in out_files:
        script = _WORKER_SCRIPT.format(
            src_path=str(_SRC_PATH), directory=str(directory), out_file=str(out_file)
        )
        procs.append(
            subprocess.Popen(
                [sys.executable, "-c", script],
                env={
                    **os.environ,
                    "USPTO_SHARED_RATE_LIMIT_RPS": "1000",
                    "USPTO_SHARED_MAX_CONCURRENT": "1",
                },
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        )

    for proc in procs:
        out, err = proc.communicate(timeout=30)
        assert proc.returncode == 0, err.decode()

    intervals = []
    for out_file in out_files:
        with open(out_file) as f:
            data = json.load(f)
        intervals.append((data["start"], data["end"]))

    (s1, e1), (s2, e2) = intervals
    assert e1 <= s2 or e2 <= s1
