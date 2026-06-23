# DRIVER — CONN-WEBSEARCH-1: the web-search reference connector (Release Cycle 3, spec §4)

**Cycle:** Community Release v1 — Cycle 3 (Connector plane). **Spec:** `docs/specs/SPEC_TOOL_CONNECTORS.md` §4.
**Goal:** ship the one genuinely net-new reference connector — `web_search` — completing the connector
abstraction's second reference (Hermes SNOMED + JUTE/:3031 already exist; graceful-absence already
implemented + tested at the grounding dispatcher).

## CORE DESIGN DECISION (non-negotiable — the safety posture)

`web_search` is **NON-AUTHORITATIVE BY CONSTRUCTION**. Web results are unverifiable, so the executor
**MUST NEVER clear or raise a finding** — it **ALWAYS** resolves `conforms=None` (inconclusive). It
**attaches** retrieved snippets/citations + a structured `web_support` assessment to the finding's
evidence (for the SME / withstands-gate to weigh) and surfaces them in provenance. This *structurally*
enforces spec §4's "evidence to weigh, not an authoritative floor that overrides the verdict" — a
stronger guarantee than a "don't bind it to clinical flags" convention. Present (citations attached) or
absent (unavailable note), `web_search` can **never** flip a verdict, clinical or otherwise.

## STANDING RULES (inherited)

- **Tests-first**: write the acceptance tests RED before any implementation; the deterministic suite is
  the supreme gate.
- **The frozen council/consensus seam is NEVER touched** — `runtime/council/compliance_council.py`,
  `_apply_consensus`, the `signals.py` withstands read (byte-frozen vs `acc4973`). This work is ABOVE
  the seam (grounding executor + manifest + spec registration).
- **Secrets via env, never the manifest** (`LITHRIM_WEB_SEARCH_API_KEY` / base-url env).
- **Scoped-pathspec commits**; **NEVER stage `apps/shell/src/app.jsx`** (foreign-modified).
- **Env:** run tests in the `debuglithrim` pyenv (`PYENV_VERSION=debuglithrim python -m pytest -q`);
  the `[bff]`+`[council]` extras live there. **Do not push.**

## FILES (4 source + tests)

1. **`lithrim_bench/harness/plugins.py`** — add a `web_search` `kind:tool` manifest to
   `_CORE_TOOL_PLUGINS` (alongside `etlp_jute`):
   ```python
   PluginManifest(
       id="web_search",
       kind="tool",
       tier="core",
       transport="service",
       implements="tool.mcp_server",
       service={"default_base_url": "http://localhost:8585"},  # config only; key via env
   )
   ```
   So the connector appears in `tool_plugins()` + `provenance_snapshot()` as a declared connector.

2. **`lithrim_bench/verification/tools.py`** — add `WebSearchTool`, mirroring `KbRagTool`'s structure
   (injectable `http_client`, no heavy deps at import):
   - `verify(claim, spec) -> VerificationResult`.
   - base-url from `reference.service` or env `LITHRIM_WEB_SEARCH_BASE_URL`; key from
     `reference.api_key` or env `LITHRIM_WEB_SEARCH_API_KEY` (fallback `LITHRIM_API_KEY`).
   - **Absent** key/endpoint → `VerificationResult(conforms=None, evidence={"web_search":"unavailable",
     "reason":"no key/endpoint configured", "query":...}, manifest=...)`. No network attempted.
   - **Present** → query the service; on success attach `evidence={"query", "citations":[...],
     "snippets":[...], "web_support":"supports|contradicts|none"}` and **ALWAYS `conforms=None`**.
   - **Transport error/unreachable** → `conforms=None` with the error in `evidence` (mirror KbRagTool's
     `except Exception -> conforms=None`). Never raises out; never clears.

3. **`lithrim_bench/harness/grounding.py`** — add `WebSearchGrounding(VerificationContract)`, mirroring
   `KbGrounding` BUT it **always returns the non-suppressing verdict** (`disproved=False`), attaching the
   web evidence to the verdict reason/evidence. Register:
   - `_CONTRACT_EXECUTORS["web_search"] = WebSearchGrounding`
   - add `"web_search"` to `_HTTP_CONTRACT_TYPES` (→ `transport=service` in manifest + provenance).
   - Document LOUDLY in the class docstring: a suppress executor that by construction can NEVER clear a
     finding — the structural non-authoritative guarantee.

4. **`lithrim_bench/verification/spec.py`** — additive registration (the documented minimal pattern):
   - `TOOL_WEB_SEARCH = "web_search"` constant (with a domain-neutral comment noting non-authoritative).
   - add `TOOL_WEB_SEARCH` to `_KNOWN_TOOLS`.
   - `_REQUIRED_REFERENCE_KEYS[TOOL_WEB_SEARCH] = {"query"}` (the SME pins the claim/query selector;
     `service`/`api_key`/`top_k`/`min_score`/`match` optional — mirrors `kb_rag`'s `{"namespace"}`).

## TESTS — RED first (`tests/verification/test_web_search_connector.py`, + a declaration assert)

- **A — Declaration:** `plugins.tool_plugins()` contains `web_search` (kind:tool, tier:core,
  transport:service); `plugins.provenance_snapshot()["plugins"]` contains it; core ⇒ present under a
  denying `LITHRIM_BENCH_LICENSE` (not gated).
- **B — spec wiring:** `VerificationSpec(tool="web_search", reference={"query":...}, ...)` constructs;
  omitting `query` raises the missing-keys `ValueError`.
- **C — Execution (mocked, present):** `WebSearchTool.verify()` on a recorded "supporting" service
  response returns `conforms is None` with `evidence` carrying citations/snippets/`web_support`.
- **D — Graceful-absent (key/endpoint unset):** `verify()` → `conforms is None`, evidence notes
  unavailable, NO exception, NO network call.
- **E — Transport error (mock raises):** `verify()` → `conforms is None` with the error in evidence;
  never raises, never clears.
- **F — `ground()` integration:** a `web_search` contract on a finding leaves it ACTIVE (un-suppressed)
  whether the mocked service supports / contradicts / errors.
- **G — Non-vacuous guarantee:** even a high-score *supporting* mocked response leaves `conforms is None`
  AND the finding active (proves the non-authoritative guarantee is real, not vacuous).
- **H — Leverage gate:** importing the tool/executor path does NOT import httpx/heavy stacks (mirror the
  kb_rag leverage test).

## DONE-BAR

- bare-CE green (`PYENV_VERSION=debuglithrim python -m pytest -q`) + `ruff check .` clean.
- `web_search` declares, executes (mocked) attaching evidence, fails clean when absent/erroring, and is
  STRUCTURALLY unable to flip a verdict; A–H green and non-vacuous.
- Moat untouched (`compliance_council.py` / `_apply_consensus` byte-identical; the seam-freeze guard
  passes).
- Optional: append a one-line "web_search shipped (non-authoritative-by-construction)" status to
  `docs/specs/SPEC_TOOL_CONNECTORS.md` §7.

## COMMIT

Scoped pathspec, atomic (connector + tests in one commit; the optional doc line may ride with it).
NEVER `app.jsx`. Do not push.
