# Content provenance and retrieved-text handling

This document is the written answer to the security-questionnaire line that asks
"how do you sanitize retrieved content before passing it to an AI model?" It
records what the USPTO Enriched Citation MCP does, what it deliberately does not
do, and why. (The labeling implementation lives in
`src/uspto_enriched_citation_mcp/shared/injection_scan.py`
(`RETRIEVED_TEXT_NOTE`, `scan_text`, `scan_hits`) and the server instructions'
provenance-posture paragraph in `main.py`.)

## Source corpus

Every record served by this system originates from two USPTO Open Data APIs at
`api.uspto.gov`: the Enriched Citation API v3 (AI-extracted citation metadata
from office actions, including `passageLocationText` passage locations and
`qualitySummaryText` quality summaries) and the Office Action Citations API v2
(raw Form PTO-892 / PTO-1449 citation lists). This is a curated regulatory
corpus, not the open web: there is no anonymous user-generated content in the
retrieval path. But "curated" is not "trusted" — the free-text fields are
AI-extracted by the USPTO from office-action documents, which quote arbitrary
applicant- and examiner-drafted text, so passage and summary content can carry
whatever a filing party wrote.

## What we deliberately do NOT do: strip or rewrite citation text

Patent-prosecution research depends on verbatim fidelity. A "sanitization" pass
that removes or rewrites token sequences from a cited passage or quality summary
would corrupt the exact language attorneys are retrieving. Citation text is
therefore served exactly as the USPTO API returns it, with provenance attached,
and is never mutated in the name of injection defense.

## What we do instead: structured, provenance-aware interfaces

1. **Data/instruction separation by labeling.** Every tool that returns
   free-text citation content (`Citations_search_citations_minimal`,
   `Citations_search_citations_balanced`, `Citations_get_citation_details`,
   `Citations_search_oa_citations_minimal`, `Citations_search_oa_citations_balanced`) attaches a
   machine-readable `provenance_note` stating that the text is quoted data, not
   instructions, and the server-level instructions direct the consuming model to
   report instruction-like language found inside retrieved text rather than act
   on it.
2. **Detection-only injection annotation.** A stdlib-only runtime scanner
   (`shared/injection_scan.py`) checks the free-text fields of each result for
   instruction-override, prompt-extraction, and encoding-evasion language and
   for suspicious densities of invisible Unicode (the steganography carrier).
   On a hit it attaches an `injection_scan` envelope key naming the flagged
   result by index and identifier with kind labels only — never the matched
   text. The key is absent entirely when results are clean, and the text itself
   is returned untouched.
3. **No generative model inside the server.** This MCP is a deterministic query
   proxy: tools build validated Lucene queries and relay USPTO API responses.
   No LLM runs inside the retrieval path (the "AI-extracted" enrichment happens
   upstream at the USPTO before the data reaches this server), so retrieved
   text cannot steer any in-server generative step.
4. **Content-minimizing logging.** Application logs record flow metadata only,
   with a `SanitizingFilter` (`util/logging.py`) applied at every handler.
   Security events never embed raw query text: `util/security_logger.py`
   records only a query's length plus a 12-hex-character SHA-256 fingerprint
   (`query_fingerprint`). The injection scanner follows the same precedent —
   kind labels and public identifiers may be logged or relayed, matched text
   may not.
5. **Commit-time codebase scanning (separate layer).** The `.security/`
   pre-commit prompt-injection scanner guards this repository's own source
   files at commit time. It is codebase hygiene, distinct from and
   complementary to the runtime annotation of retrieved corpus content
   described above.

## Residual-risk statement

Prompt-injection risk in this product reduces to: an office-action-derived
passage or summary contains text crafted to influence a downstream AI
assistant. The controls above ensure such text (a) reaches the assistant
clearly labeled as quoted document content with a provenance note, (b) is
flagged with kind labels when it is injection-shaped, and (c) cannot trigger
any in-server generative behavior, because there is none. We consider
stripping-based defenses inappropriate for a corpus whose value is verbatim
prosecution-record text, and labeling-plus-detection the correct control for
this threat model.
