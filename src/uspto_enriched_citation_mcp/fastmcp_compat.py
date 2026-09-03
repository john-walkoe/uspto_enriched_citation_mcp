"""FastMCP 4 / MCP SDK 2 compatibility shim: keep the `defer_loading` annotation.

WHY THIS EXISTS
---------------
Every tool here is registered with a `defer_loading` annotation — the flag
Claude's tool-search reads to decide which tools load eagerly and which are
fetched on demand. Two are eager (`Citations_search_citations_minimal`,
`Citations_get_guidance`); the other nine are deferred. That split is where
this server's context savings come from, and it is advertised in
SERVER_INSTRUCTIONS.

`defer_loading` is not an MCP spec field. Under FastMCP 3 / `mcp` 1.x it rode
the wire because `ToolAnnotations` was declared `extra="allow"`, so unknown
keys round-tripped through validation and serialization untouched.

FastMCP 4 pulls `mcp` 2.x / `mcp-types` 2.x, which strip it in TWO places:

1. `mcp_types.ToolAnnotations` no longer sets `extra="allow"`, so it inherits
   pydantic's `extra="ignore"` and the key is dropped at tool construction.

2. More fundamentally, `mcp/server/runner.py::ServerRunner._serialize` now
   passes every spec-method result through
   `mcp_types.methods.serialize_server_result(method, version, dumped)`, which
   re-validates the response against a PER-PROTOCOL-VERSION surface model
   (`mcp_types._v2025_11_25`, `mcp_types._v2026_07_28`) whose own docstring
   says: "The surface model carries `extra="ignore"`, so fields not in
   `version`'s schema are dropped from the returned dict."

Point 2 is the one that matters, and it is deliberate protocol-conformance
behavior, not an oversight: the SDK now guarantees that a server cannot emit
fields outside the negotiated version's schema. Fixing only point 1 makes the
patch look applied — `to_mcp_tool()` and a direct `ListToolsResult.model_dump()`
both show the key — while the wire output is still stripped, because the sieve
runs after both.

    ==> THIS IS A DELIBERATE SDK BEHAVIOR THIS MODULE OVERRIDES. <==

The alternative is to accept that `defer_loading` cannot cross an MCP SDK 2.x
server boundary, which would make every tool eagerly loaded. That is a product
decision; this module preserves the pre-migration behavior so the FastMCP 4
upgrade is not also a silent tool-search regression. Revisit it if the MCP
spec grows a real deferred-loading field, or if this stops being worth
maintaining across `mcp-types` releases.

WHAT IT DOES
------------
Restores `extra="allow"` on `ToolAnnotations` in the canonical type module and
in each per-version surface module, rebuilds the models that embed it
(bottom-up — a pydantic model's core schema snapshots its nested models'
schemas at class creation, and `model_rebuild(force=True)` only re-derives the
class it is called on), and clears the `@cache`d `TypeAdapter` the sieve uses.

Must run BEFORE any tool is registered; `main.py` imports it directly under
its `fastmcp` import for that reason.

Verified end-to-end through `serialize_server_result` itself — the actual
boundary — for every protocol version the SDK offers, and raises on failure.
A silent no-op here would turn the whole tool surface eagerly loaded with no
other symptom.
"""

from typing import Any

_APPLIED = False

# The one non-spec tool annotation this server depends on.
_CUSTOM_ANNOTATION = "defer_loading"


def _annotation_modules() -> list[Any]:
    """The canonical type module plus every per-protocol-version surface module.

    Discovered from the SDK's own `SERVER_RESULTS` map rather than hardcoded, so
    a new protocol version shipping in a future `mcp-types` is covered
    automatically instead of silently losing the annotation on that version.
    """
    import mcp_types
    import mcp_types._types
    from mcp_types.methods import SERVER_RESULTS

    modules: list[Any] = [mcp_types._types]
    seen = {mcp_types._types.__name__}
    for (method, _version), model in SERVER_RESULTS.items():
        if method != "tools/list":
            continue
        module = __import__(model.__module__, fromlist=["*"])
        if module.__name__ not in seen:
            seen.add(module.__name__)
            modules.append(module)
    return modules


def _patch_and_rebuild() -> None:
    from mcp_types.methods import _adapter

    # Import the FastMCP Tool subclasses so the subclass walk sees them
    # (FunctionTool is what `@mcp.tool` produces).
    import fastmcp.tools.function_tool  # noqa: F401
    import fastmcp.tools.tool_transform  # noqa: F401
    import fastmcp.tools.base as _fastmcp_tools_base

    for module in _annotation_modules():
        annotations_model = module.ToolAnnotations
        if annotations_model.model_config.get("extra") != "allow":
            annotations_model.model_config["extra"] = "allow"
        # Bottom-up: annotations -> tool -> list result.
        annotations_model.model_rebuild(force=True)
        module.Tool.model_rebuild(force=True)
        module.ListToolsResult.model_rebuild(force=True)

    # FastMCP's own Tool model and its subclasses hold the canonical
    # ToolAnnotations and snapshot the field schema independently.
    def _walk(cls: Any) -> None:
        cls.model_rebuild(force=True)
        for sub in cls.__subclasses__():
            _walk(sub)

    _walk(_fastmcp_tools_base.Tool)

    # The sieve resolves its TypeAdapter through an @cache'd helper, so the
    # rebuilt surface models are invisible to it until the cache is dropped.
    _adapter.cache_clear()


def _verify() -> None:
    """Round-trip the annotation through the real per-version sieve.

    Checks `serialize_server_result` for every protocol version the SDK
    advertises for tools/list, because that call — not `to_mcp_tool()` and not
    `ListToolsResult.model_dump()` — is what actually shapes the wire response.
    """
    from mcp_types.methods import SERVER_RESULTS, serialize_server_result

    from fastmcp.tools.base import Tool

    probe = Tool(
        name="_compat_probe",
        parameters={"type": "object"},
        annotations={_CUSTOM_ANNOTATION: True, "readOnlyHint": True},  # type: ignore[arg-type]
    )
    dumped = probe.to_mcp_tool().model_dump(
        by_alias=True, mode="json", exclude_none=True
    )
    # The 2026-07-28 surface requires the SEP-2549 cache fields and
    # `resultType`; the older surfaces ignore them. Supplying all three keeps
    # one payload valid against every version.
    payload = {
        "tools": [dumped],
        "resultType": "complete",
        "ttlMs": 0,
        "cacheScope": "private",
    }

    versions = sorted(v for (m, v) in SERVER_RESULTS if m == "tools/list")
    for version in versions:
        sieved = serialize_server_result("tools/list", version, payload)
        annotations = (sieved["tools"][0].get("annotations") or {})
        if annotations.get(_CUSTOM_ANNOTATION) is not True:
            raise RuntimeError(
                "FastMCP/mcp-types compatibility shim failed: the "
                f"`{_CUSTOM_ANNOTATION}` tool annotation did not survive the "
                f"protocol-version sieve for {version} "
                f"(annotations={annotations!r}). Deferred tool loading would be "
                "silently disabled for every tool. Refusing to start."
            )


def apply() -> None:
    """Idempotently allow custom tool annotations. Raises if ineffective."""
    global _APPLIED
    if _APPLIED:
        return
    _patch_and_rebuild()
    _verify()
    _APPLIED = True
