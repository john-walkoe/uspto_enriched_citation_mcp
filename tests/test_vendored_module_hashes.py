"""CR-D (review 2026-09-28): vendored-module drift guard.

Each module below is hand-copied (not a package dependency) into every USPTO
MCP repo that needs it — no shared import path exists because there is no
shared package on PyPI. That means nothing enforces the copies staying in
sync except a human remembering to re-vendor, so this test pins the md5 of
this repo's copy of each vendored module: if it drifts (an edit landed here
directly instead of at the canonical copy, or a re-vendor was missed) CI
goes red instead of the repos silently diverging.

Canonical copy (edit there, then copy byte-for-byte into this repo):
  - shared/uspto_shared_rate_limiter.py: **uspto_ptab_mcp is canonical**
    (ODP rate-limit wave, 2026-10-13: FIFO queue, capacity-1 bucket taken
    after the slot, 45 s wait ceiling, shared 429 cooldown). Copied
    byte-for-byte FROM uspto_ptab_mcp/src/ptab_mcp/shared/ into all four
    repos. History: this repo's copy had DIVERGED once (missing the 30 s
    wait cap) and was re-vendored 2026-09-28; do not hand-edit this copy,
    edit the PTAB copy and re-vendor here.

This repo carries no vendored copy of shared/response_bounds.py,
shared/citations.py, shared/dpapi_crypto.py or shared/uspto_hosts.py (PFW/
PTAB/FPD's OAuth and secure-storage modules this repo does not share).
`fastmcp_compat.py` is NOT vendored INTO this repo either: this repo is the
CANONICAL source of that module, vendored OUT into FPD/PFW/PTAB, so there is
no upstream copy for it to drift against here.

Re-vendoring rule: `cp` the file across verbatim, then re-run this test (and
the sibling repos' own copies of it) to confirm the md5 landed.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

_SHARED_DIR = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "uspto_enriched_citation_mcp"
    / "shared"
)

# filename -> expected md5 hex digest of this repo's vendored copy.
_EXPECTED_MD5 = {
    "uspto_shared_rate_limiter.py": "a381d6cd21d2a6b4590fe2a54daf432b",
}


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("filename, expected", sorted(_EXPECTED_MD5.items()))
def test_vendored_module_matches_recorded_md5(filename: str, expected: str) -> None:
    path = _SHARED_DIR / filename
    assert path.is_file(), f"vendored module missing: {path}"
    actual = _md5(path)
    assert actual == expected, (
        f"{filename} has drifted from its recorded md5 ({expected} -> "
        f"{actual}). If this edit was intentional, re-vendor it to every "
        "sharer named in this file's module docstring and update the "
        "constant here AND in each sibling repo's copy of this test."
    )
