"""Registration gate for the MCP prompt templates.

No prompts may be registered on the server unless CITATIONS_ENABLE_PROMPTS=true
(default off — prompts are opt-in server-side, matching the
CITATIONS_ENABLE_USER_MANAGEMENT registration-gate pattern).

Registration happens at import time, so each state runs in a subprocess.
"""

import os
import subprocess
import sys

_PROBE = (
    "from uspto_enriched_citation_mcp.main import mcp\n"
    # fastmcp.prompts.prompt was a v3 sys.modules alias for .base, removed in
    # FastMCP 4. The package re-export resolves on both.
    "from fastmcp.prompts import Prompt\n"
    "names = sorted(c.name for c in mcp.local_provider._components.values()"
    " if isinstance(c, Prompt))\n"
    "print('PROMPTS', ','.join(names) if names else 'NONE')\n"
)

_EXPECTED_PROMPTS = {
    "enhanced_examiner_behavior_intelligence_PFW_PTAB_FPD",
    "technology_citation_landscape_PFW",
    "patent_citation_analysis",
    "art_unit_citation_assessment",
    "litigation_citation_research_PFW_PTAB",
}


def _probe(extra_env: dict) -> set:
    env = {**os.environ}
    env.pop("CITATIONS_ENABLE_PROMPTS", None)
    env.setdefault("USPTO_API_KEY", "x" * 30)
    env.update(extra_env)
    result = subprocess.run(
        [sys.executable, "-c", _PROBE],
        capture_output=True, text=True, env=env, timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    line = [ln for ln in result.stdout.strip().splitlines()
            if ln.startswith("PROMPTS ")][-1]
    payload = line.split(" ", 1)[1]
    return set() if payload == "NONE" else set(payload.split(","))


def test_prompts_absent_by_default():
    assert _probe({}) == set()


def test_prompts_absent_when_explicitly_false():
    assert _probe({"CITATIONS_ENABLE_PROMPTS": "false"}) == set()


def test_prompts_registered_when_enabled():
    names = _probe({"CITATIONS_ENABLE_PROMPTS": "true"})
    assert names == _EXPECTED_PROMPTS
