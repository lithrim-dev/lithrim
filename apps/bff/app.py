"""The Lithrim shell BFF — the judge-capability API v1 (WS-5-BFF).

A small FastAPI backend-for-frontend that fronts the Python harness for the
React/Tauri shell (SPEC_PRODUCT_SHELL §5). It imports ``lithrim_bench.harness``
+ ``scripts/run_eval`` and exposes the v1 surface (SPEC §10 ratified):

    POST /v1/run-eval     {agent?, live?}  -> run_eval.run() record + folded
                                              calibration_check([record]) + council view
    GET  /v1/case         {agent?}         -> the case the shell displays (== graded)
    GET  /v1/corpus                        -> corpus.read_corpus() rows
    POST /v1/eval-pack/run {pack_id, agents[], live?}
                                           -> batch a pack via build_pack; frozen pack
                                              + run ids (UAP-3 R6, replay $0 default)
    GET  /v1/ontology     {agent?}         -> the agent's ontology JSON (working copy
                                              if a PUT wrote one, else committed seed)
    PUT  /v1/ontology     {agent?} <body>  -> validate + persist an edited ontology to a
                                              non-committed working copy (WS-5d)
    GET/PUT /v1/agent     {name?} <body>   -> assemble + persist an Agent to the config
                                              plane (UAP-1 R1; attributed + audit-logged)
    GET  /v1/judges       {agent?}         -> list each v2 role + bound model + assigned
                                              lens + derived questions + validator refs
    GET  /v1/judges/{role} {agent?, assigned_flags?}
                                           -> that judge's config + the rendered
                                              role_key_questions ($0 prompt preview); the
                                              assigned_flags query drives a live before/after
    PUT  /v1/judges/{role} <body>          -> assign a flag lens + model + validator refs;
                                              owner↔emit + snapshot 422; attributed audit
                                              (UAP-2 R2; the prompt↔ontology bridge target)
    GET  /v1/runs                          -> run-history: persisted runs newest-first,
                                              each addressable by run_id (UAP-3 R6/S-BS-56)
    GET  /v1/audit · /v1/runs/{id}/audit   -> the §2B why/when/who/what reports (UAP-1 R0)
    GET  /v1/kb/{ns}/search {q, ...}       -> KB-grounding check (WS-7b): composes over
                                              the harness KbRagTool, which fronts the
                                              backend KB at :8002/v1/kb/{ns}/search; returns
                                              the grounding verdict + the retrieved matches

Replay (``live=false``) is the default + the $0 path. ``live=true`` opts into
exactly one real, paid ``:8002`` council call (run_eval warns on stderr).

PUT /v1/ontology (WS-5d, SPEC §10:144) is clobber-safe by construction: it NEVER
writes the committed ``data/ontology/clinical_v1.json`` seed — it validates the body
(round-trip through ``ontology.from_dict`` + the S-BS-10/12 snapshot lint, import-only)
and persists to an agent-scoped working copy under the BFF out-dir. GET prefers that
working copy so a PUT then GET round-trips. The working copy is a DRAFT — it does not
feed an eval run, which still reads the committed seed (run_eval.py:118); wiring edits
into grading is a later phase (open seam, recorded at close).

Strangler-fig (SPEC_PRODUCT_SERVICE_TOPOLOGY, sequencing B): this targets the
harness, which composes over live :8002/:3031. No Mongo, no ../lithrim-backend.

Run:  uvicorn app:app --app-dir apps/bff --port 8787   (needs the [bff] extra)
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, get_args

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = REPO_ROOT / "scripts"
for _p in (str(REPO_ROOT), str(_SCRIPTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import run_eval  # noqa: E402  (scripts/ — the canonical run entry; mirrors tests/test_ws4a.py)

from lithrim_bench import picklist  # noqa: E402  (CASE-BROWSER-1: PACK_FILES enumeration)
from lithrim_bench.harness import (  # noqa: E402
    admissibility,
    corpus,
    evalpack,
    workspace,  # noqa: E402
)
from lithrim_bench.harness.audit import (  # noqa: E402
    Actor,
    AuditLog,
    AuditRecord,
    Target,
    make_actor,
)
from lithrim_bench.harness.backend import (  # noqa: E402  (PERSIST-2c the storage-backend seam)
    provenance_store_for,
    run_coro,
)
from lithrim_bench.harness.config import (  # noqa: E402
    agent_from_dict,
    agent_to_dict,
    delete_agent,
    delete_conversation,
    list_agents,
    load_agent,
    load_conversation,
    save_agent,
    save_conversation,
    seed_config_db,
)
from lithrim_bench.harness.finding_units import consolidate, score_units  # noqa: E402
from lithrim_bench.harness.judges import (  # noqa: E402
    JudgeConfig,
    delete_judge,
    list_judges,
    load_judge,
    save_judge,
)
from lithrim_bench.harness.ontology import from_dict as ontology_from_dict  # noqa: E402
from lithrim_bench.harness.ontology import load_ontology  # noqa: E402
from lithrim_bench.harness.replay import is_fresh  # noqa: E402  (CASE-BROWSER-1; import-light)
from lithrim_bench.harness.report import calibration_check  # noqa: E402
from lithrim_bench.harness.versioning import (  # noqa: E402  (PERSIST-2b config-object history)
    ledger_history,
    list_versions,
    version_at,
)
from lithrim_bench.picklist import load_case  # noqa: E402  (the case the shell displays)
from lithrim_bench.runtime.council.judge_assignment import (  # noqa: E402  (council-light; no openai)
    render_role_questions,
)
from lithrim_bench.runtime.council.judge_metric import LENS_BY_ROLE  # noqa: E402  (pure; no openai)
from lithrim_bench.verification.spec import (  # noqa: E402  (pure constants: no [verification] heavy deps)
    TOOL_DOSAGE_GROUNDING,
    TOOL_IN_ROW,
    TOOL_JUTE_GEN,
    TOOL_KB_RAG,
    TOOL_RECORD_RAG,
    TOOL_STRUCTURAL_JUTE,
)

_log = logging.getLogger("lithrim.bff")


def _reviewer_label(role: str) -> str:
    """UX-COPY: a role key → a user-facing reviewer name (faithfulness_judge → "Faithfulness
    reviewer"). User-facing copy only; the stored role key is unchanged."""
    base = (role or "").removesuffix("_judge").replace("_", " ").strip()
    return f"{base.title()} reviewer" if base else "a reviewer"


DEFAULT_AGENT = "ws0_default"
# Where PUT /v1/ontology persists edited ontologies. A non-committed working dir —
# NEVER data/ontology/ (the committed seed is the source of truth, clobber-safe).
DEFAULT_ONTOLOGY_WORKDIR = REPO_ROOT / "out" / "bff" / "ontology"
# Module-level Body singleton: the FastAPI idiom for a whole-request-body param,
# hoisted out of the default to satisfy ruff B008 (the ruff.toml allowance only
# whitelists Depends/Query; this avoids widening it).
_ONTOLOGY_BODY = Body(...)
_AGENT_BODY = Body(...)
_JUDGE_BODY = Body(...)
_CONVERSATION_BODY = Body(...)

# The persisted smart-contract validators a judge may REFERENCE + execute (never
# generate) — the verification toolbox names (verification/spec.py). Ref-only this
# cycle: per-evaluation execution is the §2A withstands-gate (UAP-3b).
_KNOWN_VALIDATORS = (
    TOOL_DOSAGE_GROUNDING,
    TOOL_STRUCTURAL_JUTE,
    TOOL_KB_RAG,
    TOOL_JUTE_GEN,
    TOOL_IN_ROW,
    TOOL_RECORD_RAG,
)


def get_config_db() -> Path:
    """The SQLite config plane the BFF resolves agents from — scoped to the ACTIVE
    workspace (switching the workspace switches agents/judges/flags/audit). Override in tests."""
    return workspace.get_active_workspace().config_db


def get_out_dir() -> Path | None:
    """Where run_eval persists its blob/sqlite — the active workspace's out dir. Override in tests."""
    return workspace.get_active_workspace().out_dir


def get_calib_corpus_path() -> Path:
    """The by-construction judge-calibration corpus the optimize trainer reads (the
    recipe=label trainset/held-out, lint-gated). Override in tests so the offline
    optimize-route test never reads the committed corpus."""
    return REPO_ROOT / "examples" / "judge_calib_v1.jsonl"


def get_ontology_workdir() -> Path:
    """Where PUT /v1/ontology persists working copies — the active workspace's ontology
    dir (never the committed seed). Override in tests."""
    return workspace.get_active_workspace().ontology_dir


def get_examples_dir() -> Path:
    """The corpus dir DELETE /v1/ontology/flags scans for a case-orphan (a committed case
    that emits the flag in expected_safety_flags). Override in tests for hermeticity."""
    return REPO_ROOT / "examples"


def get_kb_service() -> str:
    """The backend KB base URL the KbRagTool composes over (:8002). Override in tests."""
    return os.environ.get("LITHRIM_KB_SERVICE", "http://localhost:8002")


def get_kb_http_client() -> Any | None:
    """The httpx-like client KbRagTool uses for :8002 (None -> the tool creates one
    lazily; tests inject a fake so no live call is made)."""
    return None


def _jute_base_url() -> str:
    """The JUTE mapper base URL the ingest connects to. The mapper is an OPT-IN add-on
    (a separate ``../etlp-mapper`` service the user runs), so the URL is configurable:
    ``LITHRIM_JUTE_URL`` if set (e.g. ``http://host.docker.internal:3031`` for a host-run mapper,
    or ``http://jute:3000`` — the bundled compose service, which listens on :3000 in-network and
    publishes host :3031 for debugging), else the ``etlp_jute`` plugin manifest's default
    (``http://localhost:3031`` — the ONE place the default lives).

    Read at CALL time (no import-time capture) so Docker env / a live override is honored.
    BYTE-COMPAT: unset → the manifest default, identical to the prior hardcoded localhost:3031.
    It is configuration, not a secret — and never logged."""
    from lithrim_bench.harness import plugins

    return os.environ.get("LITHRIM_JUTE_URL") or plugins.etlp_jute_default_base_url()


def _resolve_run_backend(req: RunEvalRequest) -> tuple[bool, bool]:
    """LAUNCH-PREP D1: map a run request to the (live_http, in_process) backend pair.

    The OSS core is self-contained — a human's explicit paid run defaults to the
    bundled in-process v2 council (BYO Azure/Claude key), so NO ``:8002``/lithrim-backend
    and NO Mongo are needed. ``LITHRIM_COUNCIL_BACKEND`` selects the backend the shell's
    "Run live" button drives:
      - unset / ``in_process`` (the OSS default) -> the bundled council
      - ``http``                                 -> opt-in to a live ``:8002`` deployment
    An explicit ``in_process=true`` (CLI/SDK) always runs in-process; replay stays ``$0``.

    A-SAFE: this resolves only the HUMAN's paid-run backend at ``run_eval_endpoint``; it
    does NOT touch the agent loop's deny-hook/allowlist (apps/bff/agent/loop.py) — the
    chat stays replay-only / ``$0``."""
    if req.in_process:
        return (False, True)
    if req.live:
        if os.environ.get("LITHRIM_COUNCIL_BACKEND", "in_process") == "http":
            return (True, False)
        return (False, True)
    return (False, False)


def get_collections_db() -> Path:
    """The doc-shim DB run-provenance blobs persist to / read from (PIPELINE_RUNS) —
    the active workspace's. Override in tests so the run-audit read is hermetic."""
    return workspace.get_active_workspace().collections_db


def get_actor() -> Actor:
    """The dev-default 'who' for a write with no X-Actor header. An honest, NON-SME
    handle (monitor N5) — a real SME attributes via the X-Actor header. Override in
    tests / deployment. The §2B invariant: no config write is silently un-attributed."""
    return Actor(type="system", id="dev-default")


def _resolve_actor(x_actor: str | None, default: Actor) -> Actor:
    """The X-Actor header (a real SME handle) wins; else the configured dev default."""
    return make_actor(x_actor) if x_actor else default


def _resolve_ontology_path(agent, workdir: Path) -> tuple[Path, str]:
    """Prefer the working-copy DRAFT a PUT /v1/ontology wrote (R3 draft→grade), else
    the committed seed. Returns (path, source) where source is 'draft' | 'committed'.
    Shared by GET /v1/ontology and POST /v1/run-eval so read + grade resolve identically."""
    wc = Path(workdir) / f"{agent.name}.json"
    if wc.exists():
        return wc, "draft"
    return agent.ontology_abspath(), "committed"


def _current_grade_signature(agent, *, db_path: Path, workdir: Path, out_dir: Path | None):
    """The grade signature POST /v1/run-eval's grade would stamp RIGHT NOW — for the case
    browser's baseline-freshness dot (CASE-BROWSER-1). Assembled with the SAME shared code
    the grade uses (``grade_signature_inputs``, called by scripts/run_eval.py main) over the
    SAME resolved inputs (draft→committed ontology via ``_resolve_ontology_path``, the
    workspace out_dir's pinned demos), INCLUDING run_eval's exact ``or None`` threading —
    ``grade_signature`` embeds assignments/models RAW, so hashing ``{}`` where the grade
    passes ``None`` would misreport every pre-authoring baseline as stale. The lens authority
    is the ACTIVE-WORKSPACE pack (S-BS-154), matching the grade subprocess's env-bound pack.
    Returns ``None`` when unassemblable (e.g. no ontology) — the caller renders "unknown",
    never a guess."""
    from lithrim_bench.harness import pack as pack_mod
    from lithrim_bench.harness.replay import demo_digests, grade_signature, grade_signature_inputs

    try:
        cc = agent.eval_profile.council_config or {}
        lenses = pack_mod.pack_lenses(workspace.get_active_workspace().pack)
        si = grade_signature_inputs(db_path, cc, lenses=lenses)
        ontology_path, _src = _resolve_ontology_path(agent, workdir)
        return grade_signature(
            json.loads(Path(ontology_path).read_text()),
            assignments=si["assignments"] or None,
            models=si["models"] or None,
            council_config=cc,
            criteria=si["criteria"] or None,
            samples=si["samples"] or None,
            temperatures=si["temperatures"] or None,
            demo_digests=demo_digests(out_dir),
        )
    except Exception:  # noqa: BLE001 — a freshness read must never 500 the browser
        return None


def _agent_code_families(agent, workdir: Path) -> dict:
    """FINDING-UNITS-1: the agent's ontology-declared ``code_families`` (optional top-level
    block) — the ONLY authority on which codes are consolidation siblings. Resolved through
    the SAME draft→committed path the grade uses, so units cluster by the ontology that
    actually voted. Absent/unreadable → {} (the clerk is inert; units are 1:1 with findings)."""
    try:
        path, _src = _resolve_ontology_path(agent, workdir)
        return json.loads(Path(path).read_text()).get("code_families") or {}
    except Exception:  # noqa: BLE001 — a missing/odd ontology must never fail the batch
        return {}


def _agent_gradeable_codes(agent, workdir: Path) -> set[str] | None:
    """LAYER3-DESCOPE-1: the set of GRADEABLE flag codes in the agent's resolved ontology
    (draft→committed, the same path the grade uses). A code with ``gradeable: false`` is a
    descoped/reference flag — grounding already skip-logs it from ``active`` (S-BS-10); this
    lets the scorecard drop it from the GOLD denominator too, so a descoped axis is not a
    permanent FN. Returns ``None`` (inert — do not filter) when the ontology is
    absent/unreadable or declares no flags, so a missing ontology never silently empties gold."""
    try:
        path, _src = _resolve_ontology_path(agent, workdir)
        flags = json.loads(Path(path).read_text()).get("flags") or []
        if not flags:
            return None
        return {f["flag"] for f in flags if f.get("gradeable", True)}
    except Exception:  # noqa: BLE001 — a missing/odd ontology must never fail the batch
        return None


def _strict_readiness(strict_param: bool = False) -> bool:
    """Strict readiness is OPT-IN (annotate-by-default): the ``strict`` request field OR the
    ``LITHRIM_BENCH_STRICT_READINESS`` env flag. When on, a grade whose config would let a
    declared fact-check silently not fire is REFUSED (409) rather than graded-and-annotated."""
    if strict_param:
        return True
    return os.environ.get("LITHRIM_BENCH_STRICT_READINESS", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _compute_readiness(agent, ontology_path: Path, ontology_source: str, pack: str | None):
    """The agent↔pack readiness report for THIS grade config (a :class:`ReadinessReport`, or
    ``None`` if it can't be assessed).

    A pure, offline, ``$0`` preflight (``harness.readiness``): does the agent's RESOLVED ontology
    actually carry every verification-contract the pinned pack declares, each with a registered
    executor + a permitted tool? It reads the same inputs ``ground()`` receives and returns
    advisory metadata — it never touches the frozen grade seam. Failure to assess is swallowed to
    ``None`` so the preflight can never break a grade."""
    from lithrim_bench.harness import readiness as _readiness_mod

    try:
        return _readiness_mod.resolve_and_assess(
            agent_name=agent.name,
            agent_ontology_path=ontology_path,
            ontology_source=ontology_source,
            pack=pack or workspace.DEFAULT_PACK,
        )
    except Exception:  # noqa: BLE001 — readiness is advisory; a preflight error never blocks grading
        return None


# NARR-7 / G3 — backtick-quoted collection names in an extraction_rules hint (e.g. "one case per
# `comments`"). The AGENT channel for naming the iterated collection (the SDK-MCP tool schema is
# frozen, no expected_count knob), so an arbitrary {issues,comments}-shaped dump can ingest.
_ITERATED_COLLECTION_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*)`")


def _ingest_timeout_s() -> float:
    """The bound on the BYO-data ingest extractor (CE-INGEST-FASTFAIL). Default 30s,
    configurable via ``LITHRIM_INGEST_TIMEOUT`` (seconds). A non-numeric / <=0 value
    falls back to the 30s default — the bound is never silently disabled."""
    raw = os.environ.get("LITHRIM_INGEST_TIMEOUT")
    if not raw:
        return 30.0
    try:
        val = float(raw)
    except ValueError:
        return 30.0
    return val if val > 0 else 30.0


def _run_bounded(fn: Any, timeout_s: float) -> Any:
    """Run ``fn()`` with a hard wall-clock bound (CE-INGEST-FASTFAIL).

    A DAEMON worker thread + ``thread.join(timeout)`` — NOT ``signal.alarm`` (which is
    main-thread-only and would not fire under a uvicorn worker thread, the live deploy).
    On timeout we raise ``TimeoutError``; the worker is a daemon, so the abandoned
    runaway attempt blocks neither this caller (we fast-fail now) NOR process exit (its
    result is never read and it cannot pin — the PIN is downstream of this call). An
    exception raised inside ``fn`` is re-raised on the calling thread (the convergence
    paths surface exactly as before).
    """
    import threading

    box: dict[str, Any] = {}

    def _runner() -> None:
        try:
            box["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 — re-raised on the caller below
            box["error"] = exc

    worker = threading.Thread(target=_runner, daemon=True)
    worker.start()
    worker.join(timeout_s)
    if worker.is_alive():
        raise TimeoutError(
            f"ingest timed out after {timeout_s:g}s — the extractor could not converge "
            f"to a valid case structure; simplify the extraction rules, reduce the JSON, "
            f"or name the join key explicitly; nothing pinned"
        )
    if "error" in box:
        raise box["error"]
    return box.get("value")


def _build_authoring_lm():
    """The DSPy LM that AUTHORS the ingest JUTE transform — the user's CONFIGURED provider.

    INGEST-LM-1. The generate→refine loop needs a DSPy LM to write the transform YAML (the
    live gate is :3031; the LM only writes YAML, never grades). The BFF sets no global LM, so
    we resolve one from the configured provider IN ORDER:

      1. ``dspy.settings.lm`` — an explicit global LM (offline tests / an injected predictor).
         UNCHANGED short-circuit (byte-identical to before).
      2. the configured CHAT/assistant provider (``_chat_provider_config()`` → a litellm
         ``dspy.LM``: ``azure``/``openai``/``gemini``/``bedrock``/``openai_compatible``). Azure
         threads ``api_version`` (the litellm DeploymentNotFound wall); ``None`` (anthropic-SDK
         chat / unset) skips to (3).
      3. the configured GRADING provider via ``build_judge_lm("risk_judge")`` — respects the
         per-role/global binding the user set (azure → azure with api_version; explicit
         byo-claude → the CLI LM). The v2 default is Azure, NOT the CLI.

    The blind ``build_claude_cli_lm()`` default is GONE — ``claude`` is reached ONLY via an
    EXPLICIT byo-claude config through ``build_judge_lm`` (step 3), never as the fallback. If
    NOTHING is configured / no LM is constructible, raise a clear ``RuntimeError`` telling the
    human to configure a provider in Connect AI (the ingest handler surfaces it as guidance and
    pins nothing) — never a cryptic ``FileNotFoundError: 'claude'``.

    SDK-free at app.py import: ``dspy`` / the agent-loop chat config / ``build_judge_lm`` are
    all imported lazily HERE, so importing ``app`` stays litellm/dspy-free.
    """
    import dspy

    settings_lm = dspy.settings.lm
    if settings_lm is not None:
        return settings_lm  # explicit global LM — offline / injected; byte-identical short-circuit

    # the configured CHAT provider (the conversational authoring brain) — a litellm dspy.LM.
    from agent.loop import _chat_provider_config, _litellm_prefix  # lazy: keep [agent] off import

    chat_cfg = _chat_provider_config()
    if chat_cfg:
        provider = (chat_cfg.get("provider") or "").strip().lower()
        model = chat_cfg.get("model") or ""
        lm_kwargs: dict[str, Any] = {"temperature": 0, "max_tokens": 4096}
        if chat_cfg.get("api_key"):
            lm_kwargs["api_key"] = chat_cfg["api_key"]
        if chat_cfg.get("api_base"):  # azure / openai_compatible
            lm_kwargs["api_base"] = chat_cfg["api_base"]
        if provider == "azure":
            # CONNECT-AI-AZURE-1 parity: an azure LM needs an api_version (the chat loop threads
            # it too); default to the council default when the chat config left it empty.
            from lithrim_bench.runtime.council.settings import settings as _council_settings

            lm_kwargs["api_version"] = (
                (chat_cfg.get("api_version") or "").strip()
                or _council_settings.AZURE_OPENAI_API_VERSION
            )
        try:
            return dspy.LM(f"{_litellm_prefix(provider)}/{model}", **lm_kwargs)
        except Exception as exc:  # noqa: BLE001 — surfaced as actionable guidance below
            raise RuntimeError(
                f"could not build the ingest authoring LM from the configured chat provider "
                f"({provider!r}): {exc}. Configure a provider in Connect AI; nothing pinned."
            ) from exc

    # the configured GRADING provider — respects the per-role/global binding (azure → azure;
    # explicit byo-claude → the CLI LM). claude is reachable ONLY via this explicit config.
    from lithrim_bench.runtime.council.judges_dspy import build_judge_lm

    try:
        return build_judge_lm("risk_judge")
    except Exception as exc:  # noqa: BLE001 — no provider configured → actionable guidance
        raise RuntimeError(
            f"no LM available to author the ingest transform — configure a provider in "
            f"Connect AI (chat or grading): {exc}; nothing pinned"
        ) from exc


def _infer_iterated_count(sample: Any, extraction_rules: str = "") -> int:
    """Infer expected_count = the iterated SOURCE collection's length (NARR-7 / G3).

    Resolution: (1) a backtick-quoted top-level key in extraction_rules whose value is a list
    (the agent's iterated-collection hint), else (2) the StoryWorld enhanced_scenes count
    (UNCHANGED), else (3) a bare top-level list length, else 1. A non-list dict with no hint
    yields 1 — so a multi-record transform is REJECTED by the gate, not silently mis-counted.
    """
    if isinstance(sample, dict) and extraction_rules:
        # (1) an explicit backtick-quoted top-level key (the precise hint).
        for name in _ITERATED_COLLECTION_RE.findall(extraction_rules):
            value = sample.get(name)
            if isinstance(value, list):
                return len(value)
        # (1b) NARR-7.1: a bare top-level list-key named as a WHOLE WORD (singular or plural) in the
        # rules — so the agent's NATURAL "one case per comments" resolves without exact backticks.
        # Disambiguate: if several list keys are named, prefer one after per/each/every; if still
        # ambiguous, do NOT guess (fall through to 1 → the gate rejects, never a silent mis-count).
        list_keys = {k: len(v) for k, v in sample.items() if isinstance(v, list) and v}
        named = [
            k
            for k in list_keys
            if re.search(rf"\b{re.escape(k.rstrip('s'))}s?\b", extraction_rules, re.IGNORECASE)
        ]
        if len(named) > 1:
            named = [
                k
                for k in named
                if re.search(
                    rf"\b(?:per|each|every)\b[^.;]*\b{re.escape(k.rstrip('s'))}s?\b",
                    extraction_rules,
                    re.IGNORECASE,
                )
            ]
        if len(named) == 1:
            return list_keys[named[0]]
    scenes = (
        (sample.get("resource", {}).get("metadata", {}) or {}).get("enhanced_scenes")
        if isinstance(sample, dict)
        else None
    )
    if isinstance(scenes, dict):
        return len(scenes)
    if isinstance(sample, list):
        return len(sample)
    return 1


def _load_agent(name: str, db_path: Path):
    # Build the config DB from the committed agent seeds on first use. POSTGRES-PORTABLE
    # (POSTGRES-DEADLOCK-FIX): seed when the config DB has NO agents (a query), NOT when a local
    # sqlite FILE is missing — under the Postgres plane (LITHRIM_DB_URL) the sqlite ``db_path``
    # never exists, so the old ``not db_path.exists()`` guard re-seeded on EVERY request and two
    # concurrent requests deadlocked on ``agents_history``. ``seed_config_db`` is idempotent
    # (skips existing), so a rare concurrent first-seed is safe too.
    try:
        seeded = bool(list_agents(db_path=db_path))
    except Exception:  # noqa: BLE001 — fresh/unreadable DB → treat as unseeded
        seeded = False
    if not seeded:
        seed_config_db(db_path=db_path)
    try:
        return load_agent(name, db_path=db_path)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class RunEvalRequest(BaseModel):
    agent: str = DEFAULT_AGENT
    live: bool = False  # :8002 backend council (HTTP, paid)
    in_process: bool = (
        False  # the in-process v2 Azure council (paid Azure calls) — a fresh real run
    )
    # NARR-LOOP: grade a SPECIFIC case (e.g. an ingested-corpus case) without repointing the
    # agent. Resolved via load_case's source→PACK_FILES→workspace-corpus fallback. None → the
    # agent's own dataset.case_id (back-compat). No paid knob — it only selects WHICH case.
    case_id: str | None = None
    # READINESS: opt-in strict preflight — refuse (409) to grade a config where a pack-declared
    # fact-check can't run (default False = annotate-and-grade). Also settable via env.
    strict: bool = False


class OptimizeRequest(BaseModel):
    # PAID: a bootstrap compile over the trainset + two held-out evals × the judge
    # (mirrors run_optimize's confirm_cost gate). The route refuses (422) without it,
    # so the cost-confirm is explicit — the shell surfaces an in-DOM modal (S-BS-69).
    confirm: bool = False
    limit: int | None = None  # cap each split for a cheaper smoke (per-call cost check)
    # optimize-on-subset: scope the calibration to a CHOSEN case set (the Cases-browser ids), not
    # the whole workspace. None = today's whole-workspace behaviour (back-compat, byte-identical
    # cmd). A subset is a SELECTOR, never a paid knob — confirm=true is still required. Unknown ids
    # are dropped with a note in the subprocess; an all-unknown subset → the same clean 422 refusal.
    case_ids: list[str] | None = None


class ChatTurn(BaseModel):
    # ONB-0 (S-BS-87): one prior conversation turn, client-replayed for memory. TEXT-ONLY
    # by construction — only {role, content}; `extra="forbid"` REJECTS any smuggled paid
    # knob (confirm/live/in_process) or tool arg, so history can never widen the A-SAFE
    # surface. Replayed as context (a transcript preamble), never re-executed (loop._fold_history).
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    # UAP-5b / R11: one user utterance for the conversational shell's agent loop. NO
    # paid knob — the loop's tools are author/read/REPLAY only (the agent can never
    # spend; a paid run is the human's in-DOM cost-confirm calling the existing gate).
    # ONB-0 (S-BS-87): `history` is the client-replayed prior turns (text-only ChatTurn;
    # default empty -> back-compatible). It carries NO paid field and NO tool arg — it is
    # folded into a context preamble, never re-run. (The Phase-1 `mode` field is NOT here.)
    message: str
    agent: str = DEFAULT_AGENT
    history: list[ChatTurn] = []
    # NARR-CHAT-LOOP: the case the human is exploring in the UI (the shared "active case" the
    # shell sends each turn). The loop names it in the system prompt + defaults show_case/run_eval
    # to it, so a conversational run grades the case on screen — not the agent's seed. A SELECTOR,
    # never a paid knob; None → the agent's own dataset.case_id (back-compat).
    active_case: str | None = None


class ConversationRequest(BaseModel):
    # PERSIST-CONV: the durable conversation thread — the chat prose (the {role, text?, parts?}
    # message list the shell holds) persisted per-(workspace, agent) so a browser refresh no
    # longer wipes it. NO paid knob + NO X-Actor: this is high-frequency per-turn UX state, a
    # PLAIN upsert, NOT an audited config write (the config WRITES inside a conversation are
    # audited on their own routes; auditing every turn would bloat the §2B log).
    agent: str = DEFAULT_AGENT
    thread: list = []


class GroundingContractRequest(BaseModel):
    # EVAL-FLOW (W1b): the ContractBuilder card's direct, audited grounding-contract write — the
    # SAME store the grade consumes (ontology.verification_contracts), the SAME write path the
    # add_grounding_contract chat tool uses. $0 config write, NO paid knob (the card never runs).
    flag_code: str
    contract_type: str
    params: dict = {}
    question: str = ""
    version: str = ""
    agent: str = DEFAULT_AGENT


class AuthoredToolRequest(BaseModel):
    # TOOL-AUTHOR-1: declare a kind:tool connector into the per-workspace config plane. `manifest`
    # is the PluginManifest (no secrets — a connector key rides env via /v1/connector/config); the
    # optional `bind` wires the tool into a judge's flag {flag_code, authority, contract_type, params}.
    manifest: dict
    bind: dict | None = None
    agent: str = DEFAULT_AGENT
    rationale: str = ""


class CriterionJuteGenerateRequest(BaseModel):
    # CRITERION-JUTE-1d: the orchestration request for the SME tool-grounded criterion loop — pick a
    # tool+call, seed generation with a plain-English criterion, gate the candidate arguments_jute
    # over the bidirectional subsumption corpus, PREVIEW ($0), then PIN on pass. Mirrors the
    # _ingest_cases preview/commit split: commit=False returns the argshape + gate report and writes
    # NOTHING; commit=True + a PASSING gate pins ONE mcp_call + arguments_jute contract (1a's
    # _pin_arguments_jute fills the sha256) via the SAME frozen put path; a FAILING gate 422s.
    flag_code: str
    tool: str
    call: str
    criterion: str = ""
    sample_case: dict = {}
    n_generations: int = 3
    authority: str = "corroborated"
    match: str = "subsumedBy"
    commit: bool = False
    agent: str = DEFAULT_AGENT
    rationale: str = ""


# META-VERDICT-1: the closed judge-fallacy taxonomy (Clinical Scribe Review's "Judge Fallacy" column).
# A clinician naming WHY the automated judge erred — the dissent's typed reason. Closed by
# construction: an out-of-enum code 422s at the model boundary (pydantic), never a free string.
JudgeFallacyCode = Literal[
    "Hallucination Blindness",
    "Reference Bias",
    "Metric Conflation",
    "Risk-Severity Blindness",
    "Boundary Violation",
]
JUDGE_FALLACY_CODES: tuple[str, ...] = get_args(JudgeFallacyCode)


class MetaVerdictRequest(BaseModel):
    # META-VERDICT-1 (SPEC_CLINICAL_SCRIBE_SELF_SERVE §4 P0): a physician's INDEPENDENT verdict +
    # judge meta-audit on a run — Clinical Scribe Review's Layer-3 (HITL clinical validator). The clinician
    # records their own pass/fail, whether they AGREE with the council, and — when they dissent —
    # the judge's named fallacy. $0, no paid knob: this is an immutable AuditRecord, not a grade.
    run_id: str
    human_verdict: Literal["pass", "fail"]
    agrees_with_council: bool
    judge_fallacy_code: JudgeFallacyCode | None = None
    rationale: str = ""


class ConnectorConfigRequest(BaseModel):
    # NARR-6 P1a: the StoryWorld admin connector config. The key is validated with a
    # read-only Test, then written ONLY to the gitignored .connector_env (§8.2) — never
    # SQLite/manifest/git/the response.
    connector_id: str = "storyworld_admin"
    base_url: str
    x_api_key: str


# R2a: a judge role id is lowercase snake (it becomes an env-var suffix — the pattern is the
# injection guard AND makes suffix→role inversion exact). Shared by every role-carrying request.
_ROLE_ID_PATTERN = r"^[a-z][a-z0-9_]{0,63}$"


class ProviderConfigRequest(BaseModel):
    # CE-PROVIDER-BACKEND (Build A, SPEC_COMMUNITY_EDITION §3): configure the user's LLM
    # provider key IN-APP. Mirrors ConnectorConfigRequest's secret hygiene — the key is
    # read-only test-probed, then written ONLY to the gitignored repo-root .provider_env
    # (never SQLite/manifest/git/the response/logs). `plane`: "grading" binds the council's
    # judge LM; "assistant" binds the chat-authoring provider. `role` (optional) targets one
    # grading judge's per-role model; absent → all three roles share `model`.
    # PROVIDER-CENTER-A (S-BS-MR1a-CROSSPROVIDER): the provider set broadens to gemini / bedrock /
    # openai_compatible (the litellm path speaks them). A grading config WITH a `role` + one of these
    # new types writes the GENERIC per-role binding (LITHRIM_LLM_{PROVIDER,MODEL,API_KEY,API_BASE}_
    # <ROLE>) so each judge can run on ANY configured provider — the cross-provider-per-role unlock.
    plane: Literal["grading", "assistant"] = "grading"
    provider: Literal["openai", "azure", "anthropic", "gemini", "bedrock", "openai_compatible", "composo"]
    api_key: str
    endpoint: str | None = None  # Azure endpoint (api_base) — required for provider="azure"
    model: str | None = None
    # R2a: any validated judge role id (authored roles included), not just the trio.
    role: str | None = Field(default=None, pattern=_ROLE_ID_PATTERN)
    # CONNECT-AI-AZURE-1: the OPTIONAL Azure ``api_version`` — the global trio threads it; a UI-only
    # Azure setup (per-role grading / chat) needs it too or litellm hits the api-version /
    # DeploymentNotFound wall. None ⇒ leave the settings default (AZURE_OPENAI_API_VERSION).
    # Non-azure providers ignore it.
    api_version: str | None = None


class StoryworldIngestRequest(BaseModel):
    # NARR-6 P1b: the real-field batch ingest. base_url + key load from .connector_env / env;
    # no secret rides the request body.
    limit: int = 50
    offset: int = 0
    agent: str = DEFAULT_AGENT


# NARR-6: where the StoryWorld connector secret + sidecar live (gitignored, per active workspace).
_CONNECTOR_ENV_NAME = ".connector_env"
_CONNECTOR_SIDECAR_NAME = "connector.json"
_STORYWORLD_KEY_VAR = "STORYWORLD_API_KEY"
# §8.1 PII: structurally-dropped session keys (child identity + reader free-text) — never enveloped.
_STORYWORLD_PII_KEYS = ("child_name", "age", "reader_note", "reader_feedback", "child_age")

# CE-PROVIDER-BACKEND (Build A, SPEC §3.1): the user's LLM provider key is written ONLY to a
# gitignored `.provider_env` (NEVER SQLite/manifest/git/the response/logs). Loaded into
# os.environ at BFF startup (mirrors _load_live_env) so subprocess grades inherit it; the in-process
# council `settings` singleton is refreshed in place on each write so build_judge_lm sees a new key
# with no restart. Per-plane non-secret status (provider/model/endpoint/last_tested) lives in a
# gitignored `.provider_status.json` sidecar so GET /v1/provider/status survives a restart.
#
# CONFIG-PERSIST-1: WHERE these live is a configurable directory (``LITHRIM_PROVIDER_ENV_DIR``),
# default ``REPO_ROOT`` for dev back-compat. docker-compose defaults it to ``/app/out`` (the named
# volume) so the in-app-configured keys + judge/chat bindings SURVIVE ``docker compose down``/``up``
# (wiped only by ``down -v``, exactly like the config DB + ``.connector_env``). Previously these sat
# at ``REPO_ROOT/.provider_env`` = ``/app/.provider_env`` = the container's writable layer, which
# ``down`` removes — so the keys/judges reset after ``up``. The constants below are the UNSET-DEFAULT
# anchors (== today when ``LITHRIM_PROVIDER_ENV_DIR`` is unset). Every read/write resolves at CALL
# time via the helpers (so the env var is honored without an import-time freeze).
_PROVIDER_ENV_NAME = ".provider_env"
_PROVIDER_STATUS_NAME = ".provider_status.json"
_MODELS_REGISTRY_NAME = ".models_registry.json"


def _provider_env_dir() -> Path:
    """The directory the in-app provider keys/bindings sidecars live in. ``LITHRIM_PROVIDER_ENV_DIR``
    if set (docker-compose defaults it to ``/app/out`` = the named volume → survives ``down``/``up``),
    else ``REPO_ROOT`` (dev back-compat, byte-identical to today). Read at call time."""
    override = os.environ.get("LITHRIM_PROVIDER_ENV_DIR")
    return Path(override) if override else REPO_ROOT


def _provider_env_path() -> Path:
    """The resolved ``.provider_env`` path (the provider keys + per-role/chat bindings). When unset
    == ``_PROVIDER_ENV_PATH`` (so existing tests that monkeypatch that constant still work)."""
    override = os.environ.get("LITHRIM_PROVIDER_ENV_DIR")
    return Path(override) / _PROVIDER_ENV_NAME if override else _PROVIDER_ENV_PATH


def _provider_status_path() -> Path:
    """The resolved ``.provider_status.json`` sidecar path (non-secret per-plane status)."""
    override = os.environ.get("LITHRIM_PROVIDER_ENV_DIR")
    return Path(override) / _PROVIDER_STATUS_NAME if override else _PROVIDER_STATUS_PATH


def _models_registry_path() -> Path:
    """The resolved ``.models_registry.json`` model-pool sidecar path."""
    override = os.environ.get("LITHRIM_PROVIDER_ENV_DIR")
    return Path(override) / _MODELS_REGISTRY_NAME if override else _MODELS_REGISTRY_PATH


def _write_sidecar(path: Path, text: str) -> None:
    """Write a provider-plane sidecar, creating the parent dir if missing (the volume root exists, but
    a custom ``LITHRIM_PROVIDER_ENV_DIR`` may not). NEVER logs the content — these carry secrets."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


# The unset-default anchors (== today). Existing tests monkeypatch these; the resolvers above fall
# back to them whenever ``LITHRIM_PROVIDER_ENV_DIR`` is unset, so a write/read is byte-identical to
# the pre-CONFIG-PERSIST-1 behavior unless the env var relocates the dir.
_PROVIDER_ENV_PATH = REPO_ROOT / _PROVIDER_ENV_NAME
_PROVIDER_STATUS_PATH = REPO_ROOT / _PROVIDER_STATUS_NAME
# MODEL-REGISTRY-1a (SPEC_COMMUNITY_EDITION §8): the configured-model POOL — a registered model is a
# first-class, reusable, capability-aware entity (the LiteLLM ``model_list`` pattern), decoupled from
# the judge role. The non-secret metadata (id/provider/model/endpoint/capabilities/last_tested/
# bound_roles) lives in this gitignored repo-root sidecar; the SECRET rides Build A's ``.provider_env``
# under a per-model namespaced WRITE-ONLY var (``_model_key_var`` — never SQLite/manifest/git/the
# response/logs/this sidecar). A role BINDS to a pool entry, reusing the Build A env-var mechanism.
# CONFIG-PERSIST-1: the unset-default anchor (== today); resolved at call time via
# ``_models_registry_path()`` so it follows ``LITHRIM_PROVIDER_ENV_DIR`` into the volume.
_MODELS_REGISTRY_PATH = REPO_ROOT / _MODELS_REGISTRY_NAME


def _load_connector_env(ws) -> dict[str, str]:
    """Parse the active workspace's gitignored ``.connector_env`` (KEY=value; mirrors
    ``grade.py:_load_env``). Missing file -> empty. Secrets stay on disk, never the config plane."""
    env: dict[str, str] = {}
    path = ws.dir / _CONNECTOR_ENV_NAME
    if not path.exists():
        return env
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        env[key.strip()] = val.strip()
    return env


def _read_connector_sidecar(ws) -> dict:
    path = ws.dir / _CONNECTOR_SIDECAR_NAME
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def _prepare_storyworld_session(session: dict) -> list[dict]:
    """NARR-6 P1b / CONN-2 sample-prep (endpoint-side; runs BEFORE _to_envelope + the frozen
    _ingest_cases).

    The ingest unit is the per-call LLM generation record (``llm_calls``) — the richest gradeable
    artifact: one eval case per call, carrying the model OUTPUT (``response_preview``) +
    ``finish_reason`` (incl. the ``content_filter`` safety signal) + ``model``, with ``purpose``
    mapped to ``source``. The live StoryWorld deployment returns ``llm_calls`` at the TOP LEVEL
    (the test fixture nests it under ``metadata``); read top-level first, fall back to metadata.
    §8.1 PII: ``child_name``/``age``/reader free-text are NEVER read into the record (structural
    key-drop — only ``llm_calls`` + the session ids are touched), and ``redact_text`` runs over the
    response preview. A session with no ``llm_calls`` yields 0 records and is skipped clean (the
    enhancement pass ran on only a minority of sessions). The prompt is intentionally NOT carried
    (it is the input, not the SUT output, and is the heaviest PII surface).
    """
    from lithrim_bench.runtime.council.phi_redaction import redact_text

    session_id = session.get("id") or session.get("session_id") or ""
    # §8.1: the child_name KEY is structurally dropped (never read into a record); use its value
    # to ALSO scrub the name out of the carried free-text — the personalized prompt/response embed
    # it, and redact_text only catches emails/phones, not names. Residual free-text PII beyond
    # name/email/phone is best-effort.
    child_name = (session.get("child_name") or "").strip()
    name_tokens = [t for t in re.split(r"\s+", child_name) if len(t) > 1]

    def _scrub(text: str) -> str:
        t = redact_text(text or "")
        if child_name:
            t = t.replace(child_name, "[REDACTED_NAME]")
        for tok in name_tokens:  # first/last name incl. the possessive the story uses ("Noor's")
            t = re.sub(rf"\b{re.escape(tok)}('s)?\b", "[REDACTED_NAME]", t)
        return t

    llm_calls = session.get("llm_calls")
    if not isinstance(llm_calls, list) or not llm_calls:
        meta_calls = (session.get("metadata") or {}).get("llm_calls")
        llm_calls = meta_calls if isinstance(meta_calls, list) else []

    records: list[dict] = []
    for i, call in enumerate(llm_calls):
        if not isinstance(call, dict):
            continue
        records.append(
            {
                "case_id": f"storyworld_{session_id}_call{i}" if session_id else f"sw_call{i}",
                # the I/O pair: response_preview is the graded OUTPUT, prompt is the INPUT that
                # produced it (rides context via _to_envelope); both §8.1-redacted + name-scrubbed.
                "response": _scrub(call.get("response_preview") or ""),
                "prompt": _scrub(call.get("prompt") or ""),
                "session_id": session_id,
                "node": f"call{i}",
                "source": call.get("purpose"),
                "purpose": call.get("purpose"),
                "provider": call.get("provider"),
                "finish_reason": call.get("finish_reason"),
                "model": call.get("model"),
                "story_id": session.get("story_id"),
                "mode": session.get("mode"),
                "language": session.get("language"),
            }
        )
    return records


def _load_live_env() -> None:
    """Load the gitignored repo-root ``.live_env`` (``LITHRIM_API_KEY`` / ``LITHRIM_ORG_ID`` — the
    kb:read credential the live KB tools read) into ``os.environ`` at BFF startup. The BFF otherwise
    loads NO env file, so this is the one place the KB key reaches ``KbRagTool._headers``
    (``LITHRIM_KB_API_KEY`` → ``LITHRIM_API_KEY``) AND the grade subprocess (it inherits os.environ).
    ``setdefault``: an explicit env var still wins; ``.live_env`` only FILLS what is unset. Secrets
    stay in the gitignored file, never the config plane. Absent file → no-op."""
    live = Path(__file__).resolve().parents[2] / ".live_env"
    if not live.is_file():  # is_file (not exists): a bind-mount can create the path as a directory
        return
    for raw in live.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip("'\""))


def _parse_env_file(path: Path) -> dict[str, str]:
    """Parse a ``KEY=value`` env file (skip blanks/comments; strip wrapping quotes). Absent → {}.
    Guards ``is_file`` (not ``exists``): a ``docker compose`` bind-mount of a non-existent host file
    creates the target as a DIRECTORY, and ``read_text()`` on a dir raises ``IsADirectoryError`` —
    which would crash BFF startup. A non-regular-file path is treated as absent."""
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        out[key.strip()] = val.strip().strip("'\"")
    return out


def _load_provider_env() -> None:
    """CE-PROVIDER-BACKEND (SPEC §3.1 step 5): load the gitignored repo-root ``.provider_env`` (the
    in-app-configured LLM provider key + LITHRIM_LLM_PROVIDER + per-role models) into ``os.environ``
    at BFF startup, BEFORE any council import — so a restarted BFF still hands the key to subprocess
    grades AND, on first import, the council ``settings`` singleton reads it from env. Unlike
    ``_load_live_env`` this OVERWRITES (the env file is the user's last explicit in-app choice, the
    source of truth for the provider plane). Absent file → no-op. CONFIG-PERSIST-1: reads the resolved
    path (``LITHRIM_PROVIDER_ENV_DIR`` → the named volume in Docker), so a post-``up`` BFF restores the
    persisted keys + bindings into os.environ on boot."""
    for key, val in _parse_env_file(_provider_env_path()).items():
        os.environ[key] = val
    # ROLE-BINDINGS-DB: carry any legacy per-role binding out of the file into the config DB (once),
    # then hydrate os.environ from the DB (the per-role binding vars the grade reads). A binding-store
    # hiccup must never block BFF startup — the file load above already set the keys + global config.
    try:
        _migrate_provider_env_bindings_to_db()
        _hydrate_role_bindings_into_env()
    except Exception:  # noqa: BLE001
        pass


app = FastAPI(title="Lithrim judge-capability API", version="1.0.0")
# NOTE: CORS is registered LAST (below ``_auth_gate``) on purpose. Starlette runs the
# most-recently-added middleware OUTERMOST, and CORS must WRAP the auth gate so a cross-origin
# browser client gets a READABLE 401 (carrying Access-Control-Allow-Origin) instead of an opaque
# "Failed to fetch" when the gate rejects. See the CORS registration just below ``_auth_gate``.


def _bff_auth_token() -> str:
    """The inbound auth token, read PER-REQUEST from ``LITHRIM_BFF_TOKEN`` (stripped). Empty
    string ⇒ the gate is OFF. Reading env per request (not once at import) is deliberate: a
    test (or an env reload) toggles the gate without re-instantiating the app."""
    return os.environ.get("LITHRIM_BFF_TOKEN", "").strip()


@app.middleware("http")
async def _auth_gate(request, call_next):
    """Configurable inbound auth gate (BFF-AUTH-1, Community Release v1 Cycle 4).

    OFF by default — with ``LITHRIM_BFF_TOKEN`` unset/empty the gate is OPEN and every request
    passes exactly as before, so the local single-user one-command run is unchanged. Set the
    token to require it on an exposed server: every request then needs ``Authorization: Bearer
    <token>`` (preferred) or ``X-API-Key: <token>``, compared constant-time (``hmac.compare_digest``).
    The CORS preflight (``OPTIONS``) and the ``/health`` liveness probe always pass — gating them
    would break CORS / ``make health``. On a miss → 401 with a ``WWW-Authenticate: Bearer`` hint."""
    token = _bff_auth_token()
    if token and request.method != "OPTIONS" and request.url.path != "/health":
        auth = request.headers.get("authorization", "")
        # the auth-scheme token is case-insensitive per RFC 7235 (`bearer`/`Bearer`/`BEARER`);
        # match it case-folded so a standard client isn't wrongly rejected. The credential after
        # the scheme stays verbatim. Any non-Bearer scheme falls back to the X-API-Key header.
        presented = auth[7:] if auth[:7].lower() == "bearer " else request.headers.get("x-api-key", "")
        if not (presented and hmac.compare_digest(presented, token)):
            return JSONResponse(
                {"detail": "missing or invalid API token"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
    return await call_next(request)


# CORS registered LAST ⇒ OUTERMOST (see the note at app construction): it wraps ``_auth_gate`` so
# even a 401 from the gate carries Access-Control-Allow-Origin — a cross-origin SPA reads a clean
# 401 rather than an opaque CORS failure. Same-origin / vite-proxied clients are unaffected.
app.add_middleware(
    CORSMiddleware,
    # Non-localhost deploys (a VPS, a LAN host) serve the UI from another origin — make the
    # allowlist deployment config: comma-separated LITHRIM_ALLOWED_ORIGINS, localhost default.
    allow_origins=[
        o.strip()
        for o in os.environ.get(
            "LITHRIM_ALLOWED_ORIGINS", "http://localhost:5180,http://127.0.0.1:5180"
        ).split(",")
        if o.strip()
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup_load_live_env() -> None:
    """Load ``.live_env`` + ``.provider_env`` at SERVER startup, NOT at import — so importing app.py
    never mutates the process-global env. Keeps the KB wire-contract test hermetic regardless of
    import order; the running BFF (and the grade subprocess it spawns) still gets the kb:read
    credential AND the in-app-configured LLM provider key (CE-PROVIDER-BACKEND §3.1 step 5). Provider
    env loads BEFORE any council import so the council settings singleton reads it on first import."""
    _load_provider_env()
    _load_live_env()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


_RUN_EVAL_SCRIPT = REPO_ROOT / "scripts" / "run_eval.py"
_OPTIMIZE_SCRIPT = REPO_ROOT / "scripts" / "optimize_judge.py"


def _grade_via_subprocess(*, agent_name, config_db, ontology_path, collections_db, out_dir,
                          live, in_process, ws, case_id=None) -> dict:
    """Run the council-bound grade in a subprocess under the active workspace's pack
    (PACK-WS). The frozen council binds its pack at IMPORT, so a live BFF can't rebind it
    per-workspace — each grade gets a fresh process with LITHRIM_BENCH_PACK set instead, and
    the BFF process never imports the council (it stays pack-agnostic — the multi-tenant
    shape). assignments + models re-derive from the config DB inside run_eval.main()."""
    env = {**os.environ, "LITHRIM_BENCH_PACK": ws.pack}
    if ws.packs_dir:
        env["LITHRIM_BENCH_PACKS_DIR"] = ws.packs_dir
    if live:
        # CACHE-TRAP-1: a LIVE grade must actually re-sample — the DSPy LM disk cache otherwise
        # replays an identical re-run byte-for-byte at tokens=0. Scoped to THIS grade process;
        # replay/$0 paths inherit the ambient default unchanged.
        env["LITHRIM_JUDGE_CACHE"] = "0"
    cmd = [sys.executable, str(_RUN_EVAL_SCRIPT), "--agent", agent_name,
           "--config-db", str(config_db), "--emit-json"]
    if case_id:  # NARR-LOOP: grade a specific corpus case (the subprocess reloads the agent
        cmd += ["--case-id", case_id]  # from the DB, so the override must ride the CLI, not memory)
    if live:
        cmd.append("--live")
    if in_process:
        cmd.append("--in-process")
    if ontology_path:
        cmd += ["--ontology-path", str(ontology_path)]
    if collections_db:
        cmd += ["--collections-db", str(collections_db)]
    if out_dir:
        cmd += ["--out-dir", str(out_dir)]
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        # Keep the raw stderr in the server logs; show the user a plain, calm message.
        _log.error("grade subprocess failed (pack=%s): %s", ws.pack, proc.stderr.strip()[-1500:])
        # The drift-aware freshness guard REFUSING a stale $0 replay is not a server error —
        # it is the honest, expected outcome after a config change, and "try again" is wrong
        # advice for it (the replay refuses forever until a fresh PAID grade exists). Surface
        # the guard's own actionable line as 409 Conflict so the UI can say what to do.
        stale = next(
            (ln for ln in proc.stderr.splitlines() if "config changed since" in ln), None
        )
        if stale is not None:
            raise HTTPException(status_code=409, detail=stale.strip())
        # FIRST-CONTACT-1: a missing provider key is CONFIG, not a server fault — "try again"
        # can never fix it. build_judge_lm's ValueErrors all carry this marker.
        if "is unset; required to bind" in proc.stderr:
            raise HTTPException(
                status_code=422,
                detail=(
                    "No grading model is configured. Open Connect AI from the ⋯ menu "
                    "(bottom left) and connect a provider, then run the evaluation again."
                ),
            )
        raise HTTPException(
            status_code=500,
            detail="The evaluation couldn't run. Please try again.",
        )
    for line in proc.stdout.splitlines():
        if line.startswith("__GRADE_JSON__"):
            return json.loads(line[len("__GRADE_JSON__"):])
    raise HTTPException(status_code=500, detail="grade subprocess emitted no __GRADE_JSON__ record")


def _optimize_via_subprocess(*, role, ws, collections_db, out_dir, limit, case_ids=None) -> dict:
    """Run the PAID in-corpus optimize in a subprocess bound to the workspace's PACK (Phase 2).

    The calib is built from THIS workspace's OWN graded cases (in-domain, in the active pack's
    taxonomy — NOT the foreign hardcoded ``judge_calib_v1.jsonl``), so the held-out Δ is on the
    user's corpus. Mirrors :func:`_grade_via_subprocess`: the frozen council binds its pack at
    IMPORT, so optimizing a non-default-pack role must run in a fresh ``LITHRIM_BENCH_PACK``-bound
    process; the BFF process stays pack-agnostic (it never imports the council). A degenerate
    corpus (too few graded cases to split) comes back as an ``{"error": …}`` envelope → a calm 422.

    GENERALIST-1/Phase-2: hydrate the persisted per-role provider bindings into ``os.environ`` FIRST,
    so the subprocess inherits the model the SME bound this reviewer to (e.g. faithfulness→gpt-4.1)
    via ``LITHRIM_LLM_PROVIDER_<ROLE>`` — exactly like a grade. Else ``build_judge_lm`` falls back to
    the role's DEFAULT deployment, which may be un-deployed / n-less / logprob-less (faithfulness
    defaults to Llama, policy to Mistral). Idempotent; mirrors the startup hydration."""
    # a binding-store hiccup must never block the run (startup already set keys)
    with contextlib.suppress(Exception):
        _hydrate_role_bindings_into_env()
    env = {**os.environ, "LITHRIM_BENCH_PACK": ws.pack}
    if ws.packs_dir:
        env["LITHRIM_BENCH_PACKS_DIR"] = ws.packs_dir
    out_dir = Path(out_dir)
    cmd = [
        sys.executable, str(_OPTIMIZE_SCRIPT), "--role", role,
        "--collections-db", str(collections_db), "--out", str(out_dir),
        "--calib-out", str(out_dir / f"calib_{ws.name}.jsonl"), "--confirm-cost", "--emit-json",
    ]
    if limit is not None:
        cmd += ["--limit", str(limit)]
    # optimize-on-subset: pass each chosen id as its OWN --case-ids (argparse append). Only when
    # provided — None leaves the cmd byte-identical to the whole-workspace path. The subprocess
    # filters the workspace cases to this set BEFORE the deterministic split (unknown ids dropped
    # with a note; an all-unknown / split-starving subset → the existing clean 422 refusal).
    for cid in case_ids or []:
        cmd += ["--case-ids", str(cid)]
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        _log.error("optimize subprocess failed (pack=%s): %s", ws.pack, proc.stderr.strip()[-1500:])
        raise HTTPException(status_code=502, detail="The calibration run couldn't complete. Please try again.")
    for line in proc.stdout.splitlines():
        if line.startswith("__OPTIMIZE_JSON__"):
            res = json.loads(line[len("__OPTIMIZE_JSON__"):])
            if res.get("error"):  # degenerate corpus / unknown role → a calm, actionable 422
                raise HTTPException(status_code=422, detail=res["error"])
            return res
    raise HTTPException(status_code=502, detail="optimize subprocess emitted no __OPTIMIZE_JSON__ record")


@app.post("/v1/run-eval")
def run_eval_endpoint(
    req: RunEvalRequest,
    db_path: Path = Depends(get_config_db),
    out_dir: Path | None = Depends(get_out_dir),
    workdir: Path = Depends(get_ontology_workdir),
    collections_db: Path = Depends(get_collections_db),
) -> dict:
    """Drive one case end-to-end and return the eval-report payload.

    Folds ``calibration_check([record])`` into the response (run_eval.run() itself
    returns only the per-case ``calibration``; the run-level summary mirrors
    tests/test_ws4a.py). The folded summary is a degenerate N=1 DIAGNOSTIC on the
    WS-0 baseline (ece==0.5, small-N caveat) — NOT the WS-4b locked calibration gate.

    R3 (draft→grade): the run reads the agent's working-copy ontology if a PUT wrote
    one (else the committed seed), so an authored flag/threshold actually grades. The
    chosen source is surfaced as ``ontology_source`` ('draft' | 'committed').
    """
    live, in_process = _resolve_run_backend(req)
    return _grade_case(
        agent_name=req.agent, case_id=req.case_id, live=live, in_process=in_process,
        db_path=db_path, out_dir=out_dir, workdir=workdir, collections_db=collections_db,
        strict=req.strict,
    )


def _grade_case(
    *, agent_name, case_id, live, in_process, db_path, out_dir, workdir, collections_db,
    strict: bool = False,
) -> dict:
    """Grade ONE case end-to-end and return the eval-report payload (the shared body of
    POST /v1/run-eval and the batch POST /v1/cases/grade). ``case_id`` (NARR-LOOP) selects a
    specific case — e.g. an ingested-corpus case — via load_case's source→PACK_FILES→corpus
    fallback; ``None`` keeps the agent's own ``dataset.case_id``."""
    agent = _load_agent(agent_name, db_path)
    if case_id:
        # frozen dataclasses → rebuild; load_case then resolves case_id from the agent's source
        # (if present) else PACK_FILES else the active workspace's ingested corpus.
        from dataclasses import replace

        # The committed baseline FILE speaks only for the agent's OWN dataset case — replaying
        # it for a DIFFERENT case served another case's captured votes under this case's
        # identity (caught live, 2026-07-03 Docker validation) and bypassed the SIGNATURE-1
        # freshness guard. Dropping it routes the $0 replay through replay-from-provenance
        # (the persisted head + the drift-aware staleness refusal).
        _baseline = agent.dataset.baseline if case_id == agent.dataset.case_id else None
        agent = replace(agent, dataset=replace(agent.dataset, case_id=case_id, baseline=_baseline))
    if not agent.dataset.case_id:
        # NO-CASE-GUARD: a single grade with no resolvable case — an ingested-corpus agent has an
        # empty dataset.case_id (the cases live in the corpus, not bound to the agent). Fail with a
        # friendly, actionable 400 BEFORE the grade subprocess, which would otherwise surface an
        # opaque "case '' not found" 500. The cohort path is unaffected (it always passes case_id).
        hint = (
            ' Say "grade all cases" to score the whole corpus, or pick a specific case to run.'
            if _read_ingested_corpus()
            else " Select a case to evaluate first."
        )
        raise HTTPException(status_code=400, detail="No case selected to evaluate." + hint)
    ontology_path, ontology_source = _resolve_ontology_path(agent, workdir)
    # S-BS-63: thread the persisted judge authoring through to the in-process grade so
    # an authored judge re-votes with its authored lens (the static→live close). Read
    # from the SAME config DB the BFF resolves agents from (tests override get_config_db).
    judges_cfg = list_judges(db_path=db_path)
    assignments = {
        role: jc.assigned_flags for role, jc in judges_cfg.items() if jc.assigned_flags
    }
    # BYOC-1: thread the persisted per-judge ``model`` binding so a judge authored on
    # ``byo-claude`` runs on the tool-less BYO-Claude LM (the mixed-provider council);
    # roles with no/empty model stay Azure (the default, byte-identical to before).
    models = {role: jc.model for role, jc in judges_cfg.items() if jc.model}
    # Per-reviewer sampling/temperature/criterion (independent-axes model): role → k / temp /
    # criterion. Empty before any PUT /v1/judges → the per-role defaults (5/1/3) apply.
    samples = {role: jc.k for role, jc in judges_cfg.items() if jc.k is not None}
    temperatures = {
        role: jc.temperature for role, jc in judges_cfg.items() if jc.temperature is not None
    }
    criteria = {role: jc.criterion for role, jc in judges_cfg.items() if jc.criterion}
    ws = workspace.get_active_workspace()
    # PHASE2-B: derive the grade roster — the active pack's production_judges FIRST, then any
    # AUTHORED extra role (a judge created via POST /v1/judges, now in the pack snapshot + carrying
    # an assignment/model) appended — so the authored judge reaches build_trio and votes. ``None``
    # when there are no extras (the default trio, byte-identical to before). run() threads roles= →
    # build_authored_semantic_stage → build_trio.
    from lithrim_bench.harness import pack as _pack_mod
    from lithrim_bench.harness.judges import resolve_grade_roster

    # GENERALIST-1: a reviewer_roster may name a pack-declared lens role (e.g. a generalist
    # carrying the full-coverage lens) that the SME SELECTED from the UI without authoring an
    # explicit lens. Default such a role to its FULL pack lens so the selection actually grades —
    # else resolve_grade_roster drops the unauthored role and silently falls back to the panel (a
    # wrong-result footgun the honesty thesis forbids). Only seeds a roster role ABSENT from the
    # authored assignments; explicit authoring (incl. a narrower lens or a per-role k) is untouched.
    _council_config = agent.eval_profile.council_config or {}
    _pack_lenses = _pack_mod.pack_lenses(ws.pack)
    for _sel_role in _council_config.get("reviewer_roster") or []:
        if _sel_role in _pack_lenses and _sel_role not in assignments:
            assignments[_sel_role] = tuple(sorted(_pack_lenses[_sel_role]))
    # REVIEWER-MODE: the derived roster (production_judges ∪ any authored/selected extra) then the
    # per-agent single/panel override; a len==1 roster grades as the single-judge council (run()
    # threads gate_mode). An extra reviewer (GENERALIST-1) survives the override because the allow-set
    # is the DERIVED roster. Both grade paths share resolve_grade_roster (subprocess too).
    roles = resolve_grade_roster(
        _pack_mod.pack_production_judges(ws.pack),
        assignments,
        models,
        _council_config,
    )
    # READINESS preflight (agent↔pack contract coverage): computed BEFORE the (possibly paid) grade
    # so strict mode can REFUSE a degraded config instead of grading it silently. Advisory by
    # default — the report rides the record (below) so every grade honestly labels its config. Pure
    # data, no verdict impact: it sits above the frozen grade seam.
    readiness_report = _compute_readiness(agent, ontology_path, ontology_source, ws.pack)
    if readiness_report is not None and not readiness_report.ok and _strict_readiness(strict):
        raise HTTPException(
            status_code=409,
            detail={
                "error": "readiness",
                "message": (
                    "Refusing to grade: a declared fact-check can't run in this config (strict "
                    "readiness). Align the agent to the pack, or drop strict mode to grade anyway."
                ),
                "readiness": readiness_report.to_dict(),
            },
        )
    # PACK-WS: a workspace pinning a NON-default pack (or an external packs_dir) grades in a
    # SUBPROCESS bound to that pack — the frozen council binds its pack at import, so a live BFF
    # can't rebind it per-workspace. REPLAY is included: its ground() needs the pack's grounding
    # executors (e.g. healthcare's record_presence / snomed_subsumption), which the _core-bound
    # in-process BFF lacks (it would 500 on an unknown contract_type). Only the default _core
    # workspace grades in-process — the common CE path, fast, and the $0 predictor-injection tests.
    if ws.packs_dir or ws.pack != workspace.DEFAULT_PACK:
        try:
            record = _grade_via_subprocess(
                agent_name=agent_name, config_db=db_path, ontology_path=ontology_path,
                collections_db=collections_db, out_dir=out_dir, live=live, in_process=in_process,
                ws=ws, case_id=case_id,
            )
        except SystemExit as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    else:
        # CACHE-TRAP-1 (in-process twin of the subprocess env): a LIVE grade disables the DSPy
        # LM cache for the duration of this call, restored after — the BFF process env stays
        # clean and replay/$0 grades are untouched.
        _prior_cache = os.environ.get("LITHRIM_JUDGE_CACHE")
        if live:
            os.environ["LITHRIM_JUDGE_CACHE"] = "0"
        try:
            record = run_eval.run(
                agent,
                live=live,
                in_process=in_process,
                out_dir=out_dir,
                ontology_path=ontology_path,
                assignments=assignments or None,
                models=models or None,
                roles=roles,
                samples=samples or None,
                temperatures=temperatures or None,
                criteria=criteria or None,
                collections_db=collections_db,
            )
        except SystemExit as exc:  # run_eval raises this when the case is missing / replay refuses
            # The drift-aware stale-replay refusal is 409 (same as the subprocess path) — an
            # expected, actionable outcome after a config change, not a bad request.
            _status = 409 if "config changed since" in str(exc) else 400
            raise HTTPException(status_code=_status, detail=str(exc)) from exc
        except ValueError as exc:
            # FIRST-CONTACT-1: the in-process (_core default) twin of the subprocess mapping —
            # a missing provider key is CONFIG, not a server fault (caught live: the fresh-Docker
            # validation saw build_judge_lm's ValueError propagate as a bare 500 here).
            if "is unset; required to bind" not in str(exc):
                raise
            raise HTTPException(
                status_code=422,
                detail=(
                    "No grading model is configured. Open Connect AI from the ⋯ menu "
                    "(bottom left) and connect a provider, then run the evaluation again."
                ),
            ) from exc
        finally:
            if live:
                if _prior_cache is None:
                    os.environ.pop("LITHRIM_JUDGE_CACHE", None)
                else:
                    os.environ["LITHRIM_JUDGE_CACHE"] = _prior_cache
                # CACHE-TRAP-2: build_judge_lm turned dspy's process-global caches OFF for this
                # live grade. Restore them, or every later $0/replay grade in this process pays
                # full price for a cache it is entitled to use.
                with contextlib.suppress(Exception):  # a restore failure must not fail the grade
                    from lithrim_bench.harness.judge_cache import set_global_judge_cache

                    set_global_judge_cache(True)

    record.pop("_persisted", None)  # local fs/sqlite paths — internal, not API
    record["calibration_check"] = calibration_check([record])
    record["grade_path"] = record["provenance"].get("grade_path")
    record["ontology_source"] = ontology_source  # R3: which ontology graded (audit context)
    if readiness_report is not None:
        # honesty: every grade labels its config, so a silently-inert floor is visible in the record
        record["readiness"] = readiness_report.to_dict()
    record["council"] = _council_view(record)
    # CACHE-TRAP-2: a live grade that spent nothing is a replay, not a measurement — it must say
    # so on the record instead of returning as an ordinary success.
    record["cache_replay"] = _cache_replay_flag(record, live=live)
    # S-BS-56: surface the run's pipeline_run_id so the caller can address the run
    # (run-history + the run→audit leg). It lives on the graded PipelineResult's
    # provenance (replay carries the baseline's id; in_process/live carry a fresh id).
    record["pipeline_run_id"] = _pipeline_run_id(record)
    return record


def _pipeline_run_id(record: dict) -> str | None:
    """The graded run's pipeline_run_id (None if the result carries none)."""
    return ((record.get("result") or {}).get("provenance") or {}).get("pipeline_run_id")


def _cache_replay_flag(record: dict, *, live: bool) -> bool:
    """CACHE-TRAP-2: did a grade asked to run LIVE actually spend nothing?

    A live grade that made zero model calls is a cache replay, not a measurement, and it used to
    return as an ordinary success — a full 14-case arm was captured that way. Surfacing it is the
    load-bearing half of the fix: if the cache bypass ever regresses, a replayed number still
    cannot be quoted unknowingly.

    Only LIVE is accused. A $0/replay grade costing nothing is the normal path, and an ABSENT
    spend record is unknown rather than proof, so neither is flagged (never fabricate the charge).
    """
    if not live:
        return False
    cost = ((record.get("result") or {}).get("provenance") or {}).get("cost_tokens")
    if not isinstance(cost, dict) or cost.get("total") is None:
        return False
    return int(cost.get("total") or 0) == 0


# vote (PASS/WARN/BLOCK as shown to the UI) -> the judge's underlying decision, so the case
# outcome can be RE-DERIVED from the served votes (one source of truth that reflects the current
# rule table even on a $0 replay, instead of trusting a possibly-stale stored case_outcome).
_VOTE_TO_DECISION = {
    "PASS": "approve", "APPROVE": "approve",
    "WARN": "needs_review", "NEEDS_REVIEW": "needs_review",
    "BLOCK": "reject", "REJECT": "reject", "FAIL": "reject",
}


def _case_outcome_from_votes(votes: list[dict]) -> str | None:
    """Re-derive the named case outcome from the realized votes via the canonical rule table
    (``runtime.council.outcomes.derive_case_outcome``), so the headline stays coherent with the
    votes the UI shows AND with the current rule (a reviewer reject is never milder than BLOCK).
    None when there are no usable votes — the caller then falls back to the stored value."""
    from lithrim_bench.runtime.council.outcomes import derive_case_outcome

    seams = []
    for v in votes:
        dec = _VOTE_TO_DECISION.get(str(v.get("vote") or "").upper())
        if dec is None:
            continue
        var = v.get("variance")
        seams.append({
            "model": v.get("judge_role"),
            "decision": dec,
            "sampling": {"score_variance": var if isinstance(var, (int, float)) else 0.0},
            "errors": [],
        })
    return derive_case_outcome(seams) if seams else None


# stage verdict severity order + the named outcome a post-floor verdict reads as.
_STAGE_RANK = {"PASS": 0, "WARN": 1, "BLOCK": 2}
_VERDICT_TO_OUTCOME = {"PASS": "CLEAR", "WARN": "NEEDS_REVIEW", "BLOCK": "FLAGGED"}


def _floor_exception(vote_outcome: str | None, grounded: dict) -> tuple[str | None, int]:
    """FLOOR-STORY-1: cc2aa33's anti-milder-drift rule with its ONE sanctioned exception.

    The grounding floor is the single mechanism allowed to be MILDER than the votes —
    that is the product's thesis (a deterministic fact-check legitimately CLEARS council
    findings, e.g. SNOMED subsumption disproving FABRICATED_*). The exception fires only
    when the record's grounded block shows real suppressions that made the verdict milder;
    the post-floor grounded verdict is then the authoritative FINAL reading and the vote
    re-derivation stays as PROVENANCE. With no floor involvement the vote re-derivation
    stands, so a stale stored outcome milder than the votes still escalates (cc2aa33
    preserved). Returns ``(final_outcome, floor_cleared_count)``.
    """
    from lithrim_bench.runtime.council.outcomes import case_outcome_to_verdict

    suppressed = grounded.get("suppressed") or []
    gv = str(grounded.get("verdict") or "").upper()
    ov = str(grounded.get("original_verdict") or "").upper()
    if not vote_outcome or not suppressed or gv not in _STAGE_RANK or ov not in _STAGE_RANK:
        return vote_outcome, 0
    if _STAGE_RANK[gv] >= _STAGE_RANK[ov]:
        return vote_outcome, 0  # the floor did not make the verdict milder
    if _STAGE_RANK[gv] >= _STAGE_RANK.get(case_outcome_to_verdict(vote_outcome), 1):
        return vote_outcome, 0  # the votes already read at-or-below the grounded verdict
    return _VERDICT_TO_OUTCOME[gv], len(suppressed)


def _council_view(record: dict) -> dict:
    """Project the REALIZED per-judge council votes for the JudgeTab (D0).

    The votes the council actually cast on this case live in
    ``record["result"]["semantic"]["judge_votes"]`` (the live/replay grade carries
    them). This is the per-case truth — what each judge voted — not the configured
    roster. ``confidence`` is ``float | null`` (WS-6a D-E) and passed through as-is.
    The configured roster (best-effort, diagnostic-only) comes off the grade's
    provenance ``council_config.judges``.
    """
    result = record.get("result") or {}
    semantic = result.get("semantic") or {}
    votes = [
        {
            "judge_role": v.get("judge_role"),
            "vote": v.get("vote"),
            "confidence": v.get("confidence"),  # float | null (the logprob channel)
            # R2c dual-confidence: the reviewer's own self-reported decision aggregate,
            # carried side-by-side with the logprob confidence (float | null).
            "confidence_self": v.get("confidence_self"),
            "model": v.get("model"),
            "reason": v.get("reason"),
            # Per-reviewer sampling distribution (independent-axes model): THIS axis's own
            # variance + completion count. float|null — never aggregated across reviewers.
            "variance": v.get("variance"),
            "k": v.get("k"),
            # R2c: the raw per-sample decision scores (the "3B/2P" split derives from this).
            "scores_raw": v.get("scores_raw"),
            # VOTE-ERRORS: non-empty = this judge's call FAILED (excluded from consensus),
            # not a considered vote. [] on clean votes and pre-existing blobs.
            "errors": v.get("errors") or [],
        }
        for v in (semantic.get("judge_votes") or [])
    ]
    prov_council = (result.get("provenance") or {}).get("council_config") or {}
    # The named case outcome (independent-axes rule table) — the PRIMARY result the UI shows.
    # RE-DERIVED from the realized votes (single source of truth) so it can never drift milder
    # than the votes/consensus the way a stale stored value could; falls back to the stored value
    # only when no votes are present (e.g. a council error).
    vote_outcome = (
        _case_outcome_from_votes(votes)
        or result.get("case_outcome")
        or (result.get("provenance") or {}).get("case_outcome")
    )
    # FLOOR-STORY-1: the post-floor grounded verdict is the authoritative FINAL reading;
    # the pre-floor vote re-derivation survives as `council_outcome` (the flip's provenance)
    # and `floor_cleared` counts the suppressions that flipped it (0 = no flip).
    case_outcome, floor_cleared = _floor_exception(vote_outcome, record.get("grounded") or {})
    return {
        "votes": votes,
        "configured": list(prov_council.get("judges") or []),
        "case_outcome": case_outcome,
        "council_outcome": vote_outcome,
        "floor_cleared": floor_cleared,
    }


def _artifact_note(artifact: Any) -> str | None:
    """Surface the human-readable note buried in a FHIR artifact (base64 DocumentReference
    attachment, or a narrative ``text.div``) for DISPLAY — the raw ``artifact`` stays exactly
    what the council grades. None when there is nothing to decode. Pure Python on purpose:
    base64 is not a reliable JUTE builtin; JUTE is for cross-resource mapping, not trivial
    decodes. [[jute-for-data-transformations]]"""
    import base64

    # an ingested artifact may be wrapped as {"raw": "<json string>"} (the JUTE transform's shape) —
    # unwrap to the inner string so the FHIR/DocumentReference note below is still recoverable.
    if isinstance(artifact, dict) and isinstance(artifact.get("raw"), str):
        return _artifact_note(artifact["raw"])
    if not isinstance(artifact, str):
        return None
    try:
        res = json.loads(artifact)
    except (ValueError, TypeError):
        return None
    if not isinstance(res, dict):
        return None
    for c in res.get("content") or []:
        data = (c.get("attachment") or {}).get("data") if isinstance(c, dict) else None
        if data:
            try:  # FHIR convention is base64; this synthetic data stores the note as plain text
                decoded = base64.b64decode(data, validate=True).decode("utf-8")
                if decoded.strip():
                    return decoded.strip()
            except (ValueError, TypeError, UnicodeDecodeError):
                pass
            return str(data).strip() or None  # not base64 → the attachment IS the note
    text = res.get("text")
    return (text.get("div") if isinstance(text, dict) else None) or None


def _case_labeled(case: dict) -> bool:
    """HONEST-1 (H-D6): does this case carry a DECLARED label? A by-construction case
    declares ``expected_safety_flags`` (an empty list IS a declared clean-negative) and/or
    an ``expected_compliance_verdict``; a BYO/unlabeled case has neither. The serializer
    coerces ``expected_safety_flags`` to ``[]`` below, so absence is otherwise unrecoverable
    by the CaseTab — this presence test is the signal it branches on (no mislabeling
    unknown-truth as a clean negative)."""
    return (
        case.get("expected_safety_flags") is not None
        or case.get("expected_compliance_verdict") is not None
    )


def _case_has_gold(row: dict) -> bool:
    """Does this case carry a REAL gold label — a declared verdict OR a NON-EMPTY flag set?
    Stricter than ``_case_labeled``: ``_to_envelope`` stuffs ``expected_safety_flags: []`` into
    EVERY ingested case (an unlabeled placeholder, HONEST-1), so the empty list is NOT a gold.
    The SINGLE labeled-derivation both ``/v1/cases`` and the RUN-ALL-1 cohort scorecard read, so
    they can never drift (the live bug: the scorecard read a ``labeled`` key the raw envelope
    never carries → "0 labeled" on a fully-labeled corpus)."""
    return (
        row.get("expected_compliance_verdict") is not None
        or bool(row.get("expected_safety_flags"))
    )


def _corpus_golds_labeled(
    rows: list[dict], gradeable: set[str] | None = None
) -> tuple[dict[str, set], set]:
    """RUN-ALL-1: derive the cohort scorecard's per-case gold + labeled-set from the raw
    ingested envelopes (which carry NO ``labeled`` key). Pure; unit-tested over the real shape.

    LAYER3-DESCOPE-1: when ``gradeable`` is given, each case's gold is intersected with it —
    a descoped (non-gradeable) code leaves the gold denominator (grounding already keeps it out
    of ``active``, so it was an unwinnable FN). A case whose gold flags were NON-EMPTY but become
    EMPTY under the filter is dropped from ``labeled`` entirely (it is unscoreable on this panel,
    NOT a clean-negative — rescoring it clean would flip its surviving BLOCK into a verdict miss).
    ``gradeable=None`` is byte-identical to the pre-Layer-3 behavior."""
    corpus = {c.get("case_id"): c for c in rows if c.get("case_id")}
    raw_golds = {cid: set(c.get("expected_safety_flags") or []) for cid, c in corpus.items()}
    if gradeable is None:
        golds = raw_golds
        labeled = {cid for cid, c in corpus.items() if _case_has_gold(c)}
        return golds, labeled
    golds = {cid: (g & gradeable) for cid, g in raw_golds.items()}
    labeled = set()
    for cid, c in corpus.items():
        if not _case_has_gold(c):
            continue
        # a case whose only gold was descoped (non-empty raw flags -> empty filtered) is
        # unscoreable on this panel — leave it out of labeled rather than rescore it clean.
        if raw_golds[cid] and not golds[cid]:
            continue
        labeled.add(cid)
    return golds, labeled


@app.get("/v1/case")
def case_endpoint(
    agent: str = DEFAULT_AGENT,
    case_id: str | None = Query(None),
    db_path: Path = Depends(get_config_db),
) -> dict:
    """The case content — so the shell DISPLAYS the same case the council GRADES (no mockup
    mismatch). The transcript + the first artifact (raw, as graded) + a decoded human-readable
    note for display + the patient record. NARR-LOOP: a ``case_id`` selects a SPECIFIC case
    (e.g. an ingested-corpus case for "explore each case") via load_case's source→PACK_FILES→
    workspace-corpus fallback; ``None`` keeps the agent's own dataset.case_id."""
    ag = _load_agent(agent, db_path)
    target = case_id or ag.dataset.case_id
    case = load_case(target, source=ag.source_abspath())
    if case is None:
        raise HTTPException(status_code=404, detail=f"case {target!r} not found")
    artifacts = case.get("artifacts") or []
    pp = case.get("patient_profile") or {}
    artifact = artifacts[0].get("content") if artifacts and isinstance(artifacts[0], dict) else None
    return {
        "case_id": case.get("case_id"),
        # an ingested case carries the transcript on `context` (the §4.1 envelope); a
        # by-construction pack case carries it on `transcript`.
        "transcript": case.get("transcript") or case.get("context"),
        "artifact": artifact,
        "artifact_text": _artifact_note(artifact),
        "conditions": pp.get("conditions") or [],
        "expected_safety_flags": case.get("expected_safety_flags") or [],
        "injection_recipe": case.get("injection_recipe"),
        # "labeled" = carries a REAL answer (a declared verdict OR non-empty flags). An ingested
        # case has neither (its `expected_safety_flags: []` is an unlabeled placeholder, not a
        # declared clean-negative) → labeled=False, so the CaseTab shows "unknown ground truth".
        "labeled": (
            case.get("expected_compliance_verdict") is not None
            or bool(case.get("expected_safety_flags"))
        ),
    }


@app.get("/v1/corpus")
def corpus_endpoint() -> dict:
    """The correction-corpus rows (corpus-row/1). Empty list when none written yet."""
    return {"rows": list(corpus.read_corpus())}


def _read_ingested_corpus() -> list[dict]:
    """The active workspace's INGESTED cases — the §4.1 envelopes a user dropped via ingest.
    PERSIST-3a: the SSOT ``cases`` table is the source of truth (``cases_store``, the one DB
    selector); the legacy ``ws.out_dir/ingested_cases.jsonl`` is a transition fallback (a corpus
    ingested before 3a). Empty list when none. (Distinct from the correction corpus served by
    ``/v1/corpus``.)"""
    ws = workspace.get_active_workspace()
    try:
        from lithrim_bench.harness import cases_store

        rows = [r["payload"] for r in cases_store.list_cases(db_path=ws.collections_db)]
        if rows:
            return rows
    except Exception:  # noqa: BLE001 — a DB hiccup must not hide a legacy jsonl corpus
        pass
    path = ws.out_dir / "ingested_cases.jsonl"
    rows = []
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _resolve_named_case(message: str | None) -> str | None:
    """CHAT-CASE-RESOLVE-1: resolve the case the human NAMED in the chat message to a known
    ingested ``case_id``, DETERMINISTICALLY — so the grade targets that case regardless of
    whether the model passes it through ``run_eval(case_id=…)``.

    Conservative by construction: only an EXACTLY-NAMED known case resolves (an exact
    ``case_id`` substring of the message). Longest-match disambiguation — the most specific id
    wins, so a generic ``run_001`` known-case never shadows ``run_001_fabricates`` when the
    message names the latter. Pure $0 read (the ingested-case list); NEVER raises — a resolution
    failure must not break the chat (any read failure → ``None``). ``None`` on no match → the
    caller falls back to the client's ``active_case`` (byte-identical to today)."""
    try:
        known = [
            str(r.get("case_id")) for r in _read_ingested_corpus() if r.get("case_id")
        ]
    except Exception:  # noqa: BLE001 — a resolution failure must never break the chat
        return None
    msg = message or ""
    hits = [cid for cid in known if cid and cid in msg]
    if not hits:
        return None
    return max(hits, key=len)  # the most specific named case (longest match)


def _ssot_upsert_cases(ws, cases: list[dict]) -> None:
    """Dual-write newly-ingested cases into the SSOT ``cases`` table (PERSIST-3a). The jsonl
    write stays for the transition; this makes the corpus resolvable from the one DB (and, under
    ``LITHRIM_DB_URL``, from Postgres). Best-effort: a store hiccup never fails an ingest that
    already wrote its jsonl + audit row."""
    try:
        from lithrim_bench.harness import cases_store

        for c in cases:
            cid = c.get("case_id")
            if cid:
                cases_store.save_case(cid, c, source="ingested", db_path=ws.collections_db)
    except Exception:  # noqa: BLE001
        pass


# INGEST-LABELS-1: carry BYO ground-truth labels through ingestion. The JUTE transform extracts only
# GRADING fields (context, response, the ontology's required_case_fields), so author-supplied
# ``expected_compliance_verdict`` / ``expected_safety_flags`` are dropped — leaving the case UNLABELED
# ("no answer key", accuracy unscoreable). These merge them back DETERMINISTICALLY (no LM, no grade)
# by matching each produced case to its source entry by id/case_id, so the handler can report the
# HONEST labeled count (the agent never claims a label that did not land).
_BYO_LABEL_KEYS = ("expected_compliance_verdict", "expected_safety_flags")


def _source_labels_by_id(sample: Any) -> dict[str, dict]:
    """Index author-supplied ground-truth labels in the source dump by case id. Scans the top-level
    list (or any top-level list-valued key, e.g. ``runs``) for entries carrying an ``id``/``case_id``
    AND a label field; returns ``{id: {label fields present}}``. ``expected_safety_flags: []`` IS a
    label (a declared clean-negative). Pure; no labels → ``{}`` (cases stay unlabeled, byte-identical)."""
    out: dict[str, dict] = {}

    def _collect(entries: Any) -> None:
        if not isinstance(entries, list):
            return
        for e in entries:
            if not isinstance(e, dict):
                continue
            cid = e.get("id") or e.get("case_id")
            if not isinstance(cid, str) or not cid:
                continue
            labels = {k: e[k] for k in _BYO_LABEL_KEYS if k in e}
            if labels:
                out[cid] = labels

    if isinstance(sample, list):
        _collect(sample)
    elif isinstance(sample, dict):
        for v in sample.values():
            _collect(v)
    return out


def _merge_byo_labels(cases: list[dict], sample: Any) -> int:
    """Copy author-supplied labels onto produced cases by ``case_id`` (deterministic; no LM). Returns
    the count of cases that received a label — the honest number the handler reports. Absent labels →
    cases unchanged, returns 0."""
    by_id = _source_labels_by_id(sample)
    n = 0
    for c in cases:
        if not isinstance(c, dict):
            continue
        labels = by_id.get(c.get("case_id"))
        if labels:
            c.update(labels)
            n += 1
    return n


def _normalize_case_source(cases: list[dict]) -> int:
    """FLOOR-SOURCE-1: copy the source onto the canonical ``transcript`` field at INGEST so the
    graded case is self-contained. The council grade path + the per-judge withstands gate read the
    source from ``transcript`` ONLY (``ab_harness`` ``call_context.transcript``, the
    ``authored_stage`` ``case_view.transcript``, ``SourceGrounding``); an ingested agent-trace case
    carries it on ``context``. Without this copy a faithful case is graded against an EMPTY source —
    a judge spuriously raises ``UNSUPPORTED_ASSERTION`` and ``SourceGrounding`` returns
    ``disproved=False`` (its own answer tokens all ungrounded) → a WRONG BLOCK that disagrees with
    the report ``composite`` (which alone falls back ``transcript → context``).

    Normalizing ONCE here — rather than adding yet another per-consumer ``or context`` mapping (the
    anti-pattern) — makes every consumer (judges, withstands gate, ``grounding.ground()``) read ONE
    populated source. Pure, no LM, idempotent: a case that already has a non-empty ``transcript``,
    or has no/empty ``context``, is left byte-unchanged. Returns the count normalized."""
    n = 0
    for c in cases:
        if not isinstance(c, dict):
            continue
        if not _ctx_nonempty(c.get("transcript")) and _ctx_nonempty(c.get("context")):
            c["transcript"] = c["context"]
            n += 1
    return n


# INGEST-TEMPLATE-1: a registry of hand-authored, DETERMINISTIC JUTE templates for KNOWN ingest
# source shapes, routed in PREFERENCE to LM-generation. The LM re-derives the mapping for every
# shape and silently drops fields (it dropped the BYO labels — INGEST-LABELS-1 patched that in
# Python, a split-layer compromise). For a KNOWN shape a curated JUTE template is better on every
# axis: deterministic, carries the labels BY CONSTRUCTION (JUTE-pure), pinned + auditable. It is
# STILL live-gated (score_extraction) before use; a non-matching variant falls through to the
# existing REUSE/LM-gen path. LM-gen stays the fallback for NOVEL shapes (unchanged).
#
# The agent message-trace shape ``{runs:[{id, messages, final, expected_*}]}``. Proven LIVE on
# :3031 (compiles error=None; emits both labeled cases). ``joinStr("\n\n", e.messages.*.content)``
# joins system+user+tool and SKIPS the null-content assistant tool-call message — robust to
# message count (a 2-message no-tool trace maps cleanly). ``joinStr`` is an IMPLEMENTED :3031
# builtin (the jute-runtime-builtin-gap memory).
_AGENT_TRACE_TEMPLATE = "\n".join(
    [
        "$map: $ resource.runs",
        "$as: e",
        "$body:",
        "  case_id: $ e.id",
        "  response: $ e.final.content",
        # FLOOR-SOURCE-1: emit the canonical source under BOTH `transcript` (what the council grade
        # + withstands gate read) and `context` (kept for back-compat/display). The Python
        # `_normalize_case_source` is the load-bearing fix that survives `_to_envelope` stripping;
        # this keeps the curated JUTE self-contained at its own output layer.
        '  transcript: $ joinStr("\\n\\n", e.messages.*.content)',
        '  context: $ joinStr("\\n\\n", e.messages.*.content)',
        "  expected_compliance_verdict: $ e.expected_compliance_verdict",
        "  expected_safety_flags: $ e.expected_safety_flags",
    ]
)


_FLAT_NOTES_TEMPLATE = "\n".join(
    [
        "$map: $ resource.rows",
        "$as: e",
        "$body:",
        "  case_id: $ e.id",
        "  response: $ e.note",
        # FLOOR-SOURCE-1 dual-emit, same as the trace template: `transcript` is what the council
        # grade + withstands gate read; `context` kept for back-compat/display.
        "  transcript: $ e.transcript",
        "  context: $ e.transcript",
    ]
)


def _known_shape_template(sample: Any) -> str | None:
    """Curated-template registry/matcher: return a hand-authored JUTE template for a KNOWN source
    shape, else ``None``. The template is STILL live-gated (``score_extraction``) before use, and
    LM-generation is the fallback for NOVEL shapes — so this only short-circuits the shapes it is
    SURE about. Pure; conservative (a near-miss → ``None`` → the existing REUSE/LM-gen path).

    Two known shapes:
      * the agent message-trace ``{runs:[{id, messages, final, expected_*}]}`` — a dict with a
        non-empty ``runs`` list whose every entry is a dict carrying a truthy ``id``, a list
        ``messages``, and a dict ``final``;
      * the flat notes record ``{rows:[{id, note, transcript}]}`` — the decoded shape of the
        shipped ``samples/quickstart`` JSONL/CSV (FIRST-CONTACT-1: the DOCUMENTED first ingest
        is deterministic and provider-free). Scalar ``note``/``transcript`` only; labels ride
        the INGEST-LABELS-1 by-id merge, not the template."""
    if not isinstance(sample, dict):
        return None
    runs = sample.get("runs")
    if isinstance(runs, list) and runs:
        for e in runs:
            if not isinstance(e, dict):
                return None
            if not e.get("id"):
                return None
            if not isinstance(e.get("messages"), list):
                return None
            if not isinstance(e.get("final"), dict):
                return None
        return _AGENT_TRACE_TEMPLATE
    rows = sample.get("rows")
    if isinstance(rows, list) and rows:
        for e in rows:
            if not isinstance(e, dict):
                return None
            if not e.get("id"):
                return None
            if not isinstance(e.get("note"), str) or not e["note"].strip():
                return None
            if not isinstance(e.get("transcript"), str) or not e["transcript"].strip():
                return None
        return _FLAT_NOTES_TEMPLATE
    return None


def _ctx_nonempty(value: Any) -> bool:
    return bool(value) and str(value).strip().lower() not in ("", "{}", "[]", "null", "none")


def _native_eval_rows(sample: Any) -> list | None:
    """REPRO-1 R1a: rows that already ARE eval cases — the product's own corpus schema
    (``case_id`` + ``artifacts[0].content`` + a non-empty transcript/context) — import VERBATIM:
    no JUTE template, no LM, no mapper. Importing our own schema is not a transform problem, and
    a pass-through is the only path that preserves EVERYTHING (the structured record the floor
    grounds against, the BYO labels, the injection provenance) by construction.

    Conservative like ``_known_shape_template``: ANY non-conforming row → ``None`` → the curated/
    REUSE/LM-gen paths run unchanged. The other known shapes cannot collide: the agent-trace shape
    has no ``artifacts``; the flat-notes shape keys ``id``, not ``case_id``. Accepts a bare list
    (a decoded JSONL corpus arrives as ``{rows:[...]}``) or a ``rows``/``cases`` wrapper."""
    rows = sample
    if isinstance(sample, dict):
        rows = sample.get("rows") or sample.get("cases")
    if not isinstance(rows, list) or not rows:
        return None
    for e in rows:
        if not isinstance(e, dict) or not e.get("case_id"):
            return None
        arts = e.get("artifacts")
        if not (isinstance(arts, list) and arts and isinstance(arts[0], dict)):
            return None
        if not str(arts[0].get("content") or "").strip():
            return None
        if not (_ctx_nonempty(e.get("transcript")) or _ctx_nonempty(e.get("context"))):
            return None
    return rows


# REPRO-1 R1a: the structured RECORD a case supplies (the problem list / account state the
# floor grounds against) is a first-class ingest passthrough — preserved into the stored case
# independent of any contract declaration. The non-native envelope (`_to_envelope`) projects a
# fixed §4.1 shape and carries only the criteria-required `*_path` fields, silently dropping
# `patient_profile` on every template / LM path; without the record, R1b has nothing to render
# and the record-vs-note floor grades incomplete input. We copy it back OPTIONALLY (absent →
# untouched, never a rejection) — exactly the BYO-label merge pattern, so the gating invariant
# (`score_extraction`) is untouched. Generic by construction: `patient_profile` is a structural
# envelope field name (corpus-A §4.1 shape), never a clinical string.
_RECORD_PASSTHROUGH_FIELDS = ("patient_profile",)


def _source_records_by_id(sample: Any) -> dict[str, dict]:
    """Index the source dump's structured record(s) by case id — the R1a analog of
    `_source_labels_by_id`. Scans the top-level list (or any top-level list-valued key, e.g.
    `rows`/`runs`) for entries carrying an `id`/`case_id` AND a `_RECORD_PASSTHROUGH_FIELDS`
    field; returns `{id: {record fields present}}`. Pure; no record → `{}` (byte-identical)."""
    out: dict[str, dict] = {}

    def _collect(entries: Any) -> None:
        if not isinstance(entries, list):
            return
        for e in entries:
            if not isinstance(e, dict):
                continue
            cid = e.get("id") or e.get("case_id")
            if not isinstance(cid, str) or not cid:
                continue
            record = {
                k: e[k]
                for k in _RECORD_PASSTHROUGH_FIELDS
                if e.get(k) not in (None, "", [], {})
            }
            if record:
                out[cid] = record

    if isinstance(sample, list):
        _collect(sample)
    elif isinstance(sample, dict):
        for v in sample.values():
            _collect(v)
    return out


def _merge_source_record(cases: list[dict], sample: Any) -> int:
    """Copy the source record (`patient_profile`, R1a) onto produced cases by `case_id`
    (deterministic; no LM). Returns the count enriched. Absent record / no matching id → cases
    unchanged, returns 0. Never overwrites a record the envelope already carried (the native path
    keeps its verbatim record)."""
    by_id = _source_records_by_id(sample)
    n = 0
    for c in cases:
        if not isinstance(c, dict):
            continue
        record = by_id.get(c.get("case_id"))
        if not record:
            continue
        added = False
        for k, v in record.items():
            if c.get(k) in (None, "", [], {}):
                c[k] = v
                added = True
        if added:
            n += 1
    return n


@app.get("/v1/cases")
def list_cases_endpoint() -> dict:
    """NARR-LOOP — list the active workspace's INGESTED corpus (the gradeable cases a user
    dropped via ingest), so the shell can show "load all cases" and grade case-by-case. Each
    row carries enough to drive the picker without re-fetching: case_id, whether it has a label,
    a non-empty grading context (the transcript-fidelity signal the 2026-06-17 fix guards), and
    graded content. (The ``/v1/corpus`` slot serves the unrelated correction corpus.)"""
    cases = []
    for row in _read_ingested_corpus():
        cid = row.get("case_id")
        if not cid:
            continue
        arts = row.get("artifacts") or []
        cases.append(
            {
                "case_id": cid,
                # "labeled" = carries a REAL gold label; the shared _case_has_gold the cohort
                # scorecard also reads, so the two views never drift (NOT _case_labeled, which
                # counts the `expected_safety_flags: []` placeholder as a clean-negative).
                "labeled": _case_has_gold(row),
                "context_kind": row.get("context_kind"),
                "has_context": _ctx_nonempty(row.get("context")),
                "has_artifact": bool(arts and (arts[0].get("content") or "")),
            }
        )
    return {"cases": cases, "count": len(cases)}


_BROWSER_MAX_CASES = 500


def _agent_known_case_ids(agent: str, db_path: Path) -> list[str]:
    """CHAT-CASE-TOKEN-RESOLVE — the case ids ``load_case`` can resolve for this agent, in the
    SAME resolution order the browser uses (the agent's pinned source file → the legacy
    ``PACK_FILES`` fixtures → the workspace's ingested corpus; first-wins dedup). This is the
    known-case source the chat/tool layer maps a SHORT/PREFIX token against — the same list that
    backs GET /v1/cases/browser, deliberately reused so the two never drift. $0 read; never raises
    (a resolution failure → whatever ids were collected so far)."""
    ids: list[str] = []
    seen: set[str] = set()

    def _add_id(row: dict) -> None:
        cid = row.get("case_id") or row.get("id")
        if cid and cid not in seen and len(ids) < _BROWSER_MAX_CASES:
            seen.add(cid)
            ids.append(cid)

    def _jsonl_ids(path: Path):
        try:
            for line in path.open():
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
        except OSError:
            return

    try:
        ag = _load_agent(agent, db_path)
        src = ag.source_abspath()
        if src and Path(src).is_file():
            for row in _jsonl_ids(Path(src)):
                _add_id(row)
        for _pack_name, paths in picklist.PACK_FILES.items():
            for fp in paths:
                if fp.exists():
                    for row in _jsonl_ids(fp):
                        _add_id(row)
        for row in _read_ingested_corpus():
            _add_id(row)
    except Exception:  # noqa: BLE001 — a known-case read must never break the chat
        pass
    return ids


@app.get("/v1/cases/browser")
def case_browser_endpoint(
    agent: str = DEFAULT_AGENT,
    db_path: Path = Depends(get_config_db),
    collections_db: Path = Depends(get_collections_db),
    out_dir: Path | None = Depends(get_out_dir),
    workdir: Path = Depends(get_ontology_workdir),
) -> dict:
    """CASE-BROWSER-1 (UI-pass 2026-07-04 finding #1) — the browsable case list: every case
    ``load_case`` can resolve for this agent, in its EXACT resolution order (the agent's
    pinned source file → the legacy ``PACK_FILES`` fixtures → the workspace's ingested
    corpus; first-wins dedup), so the pane's Cases tab can show what's gradeable instead of
    leaving case IDs discoverable only via chat.

    Per row: the by-construction label (``labeled`` via the shared ``_case_has_gold``;
    ``defect`` = the injection_recipe's ``defect_type``, else the first expected flag —
    ``None`` on a labeled row means a first-class CLEAN negative), this agent's persisted
    ``runs`` count, and ``baseline`` — fresh | stale | none | unknown: whether the $0 replay
    would serve, judged by the head's ``grade_signature`` against ``_current_grade_signature``
    (the SAME assembly the grade stamps — never a parallel guess). ``unknown`` = a head
    exists but the current signature is unassemblable."""
    ag = _load_agent(agent, db_path)
    seen: set[str] = set()
    rows: list[dict] = []

    def _add(row: dict, source: str) -> None:
        cid = row.get("case_id") or row.get("id")
        if not cid or cid in seen or len(rows) >= _BROWSER_MAX_CASES:
            return
        seen.add(cid)
        recipe = row.get("injection_recipe")
        flags = row.get("expected_safety_flags") or []
        defect = (recipe.get("defect_type") if isinstance(recipe, dict) else None) or (
            flags[0] if flags else None
        )
        rows.append(
            {"case_id": cid, "source": source, "labeled": _case_has_gold(row), "defect": defect}
        )

    def _jsonl_rows(path: Path):
        try:
            for line in path.open():
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
        except OSError:
            return

    src = ag.source_abspath()
    if src and Path(src).is_file():
        for row in _jsonl_rows(Path(src)):
            _add(row, "pinned")
    for _pack_name, paths in picklist.PACK_FILES.items():
        for fp in paths:
            if fp.exists():
                for row in _jsonl_rows(fp):
                    _add(row, "pack")
    for row in _read_ingested_corpus():
        _add(row, "ingested")

    store = provenance_store_for(collections_db)
    counts: dict[str, int] = {}
    for d in run_coro(store.list_all(limit=_BROWSER_MAX_CASES)):
        if d.get("agent_id") == agent and d.get("case_id"):
            counts[d["case_id"]] = counts.get(d["case_id"], 0) + 1
    current_sig = _current_grade_signature(ag, db_path=db_path, workdir=workdir, out_dir=out_dir)
    for r in rows:
        r["runs"] = counts.get(r["case_id"], 0)
        if r["runs"] == 0:
            r["baseline"] = "none"
            continue
        head = run_coro(store.latest_authoritative_for(agent, r["case_id"]))
        if head is None:
            r["baseline"] = "none"
        elif current_sig is None:
            r["baseline"] = "unknown"
        else:
            r["baseline"] = "fresh" if is_fresh(head, current_sig) else "stale"
    return {
        "agent": agent,
        "cases": rows,
        "count": len(rows),
        # no silent caps: a truncated browse says so instead of reading as "everything".
        "truncated": len(rows) >= _BROWSER_MAX_CASES,
    }


class GradeCasesRequest(BaseModel):
    # NARR-LOOP: batch-grade the ingested corpus (the "evaluate all of them → report" loop).
    # case_ids None → ALL ingested cases. live/in_process are the SAME paid knobs as run-eval
    # (replay/$0 default); a paid batch is the human's call, never an agent tool.
    case_ids: list[str] | None = None
    agent: str = DEFAULT_AGENT
    live: bool = False
    in_process: bool = False
    strict: bool = False  # READINESS: opt-in strict preflight (see RunEvalRequest.strict)


class IngestPreviewRequest(BaseModel):
    # CE-INGEST-FRONTDOOR-1: the data front door. `raw` is the uploaded file/paste content; `fmt`
    # is auto-detected (by `filename` extension, else content sniff) unless named explicitly.
    # `extraction_rules` is the human's field-mapping correction channel (re-preview to refine).
    raw: str
    fmt: str = "auto"
    filename: str = ""
    extraction_rules: str = ""
    agent: str = DEFAULT_AGENT


class IngestCommitRequest(BaseModel):
    # The human APPROVED `approved_template` (returned by /preview) over `raw` — pin it + upsert.
    # None (REPRO-1 R1a): a NATIVE eval-case corpus previews with NO template (nothing to
    # approve — the rows already are cases); its commit re-detects the native shape verbatim.
    approved_template: str | None = None
    raw: str
    fmt: str = "auto"
    filename: str = ""
    extraction_rules: str = ""
    agent: str = DEFAULT_AGENT


def _is_blocked_verdict(verdict) -> bool:
    return str(verdict or "").upper() in {"BLOCK", "FAIL", "REJECT"}


def _corpus_gold_verdicts(rows: list[dict]) -> dict[str, bool]:
    """R3: per-case gold VERDICT (True = should BLOCK) from the ingested envelopes. A declared
    ``expected_compliance_verdict`` wins (the verdict-only-label corpus — a reject with no flag
    labels IS a gold BLOCK, which the bool(flags) derivation silently mis-scored); else a
    non-empty flag set implies blocked. Unlabeled cases are absent."""
    out: dict[str, bool] = {}
    for c in rows:
        cid = c.get("case_id")
        if not cid or not isinstance(c, dict):
            continue
        v = c.get("expected_compliance_verdict")
        if v is not None:
            out[cid] = str(v).strip().lower() in {"reject", "block", "fail"}
        elif c.get("expected_safety_flags"):
            out[cid] = True
    return out


def _cohort_scorecard(
    rows: list[dict], golds: dict[str, set], labeled: set,
    code_families: dict | None = None,
    gold_verdicts: dict[str, bool] | None = None,
) -> dict:
    """RUN-ALL-1: the consolidated report — compare each graded cohort row to its gold flags →
    per-case caught/missed/spurious + an aggregate flag precision/recall + verdict accuracy + a
    per-flag over/under-fire breakdown. Only LABELED cases feed the accuracy metrics (honest-
    unlabeled — never fabricate numbers on unlabeled data); an unlabeled row still shows its raw
    result. Pure over the matrix the chat already has, so the report needs zero span-matching.

    R3 (REPRO-1): also aggregates the RESEARCH read surface — ``by_judge`` (each reviewer scored
    against gold), ``majority`` (the cross-model majority, ties reported), ``judge_matrix`` (the
    case × reviewer table with raw K-splits), and ``floor`` (cleared/enforced/cannot-ground
    tallies, gold-defect clears — the must-be-zero safety property — and verdict accuracy PRE vs
    POST floor from the same rows). ``gold_verdicts`` (case → should-block) honors a declared
    expected_compliance_verdict; absent → the bool(gold-flags) back-compat derivation."""
    gold_verdicts = gold_verdicts or {}

    def _gold_blocked(cid: str, gold: set) -> bool:
        return gold_verdicts[cid] if cid in gold_verdicts else bool(gold)

    cases: list[dict] = []
    tp = fp = fn = vmatch = n_lab = 0
    by_flag: dict[str, dict] = {}
    for r in rows:
        cid = r.get("case_id")
        raised = set(r.get("findings") or [])
        row = {"case_id": cid, "verdict": r.get("verdict"),
               "labeled": cid in labeled, "raised": sorted(raised)}
        if cid in labeled:
            gold = golds.get(cid, set())
            caught, missed, spurious = gold & raised, gold - raised, raised - gold
            blocked = _is_blocked_verdict(r.get("verdict"))
            row.update({"gold": sorted(gold), "caught": sorted(caught),
                        "missed": sorted(missed), "spurious": sorted(spurious),
                        "verdict_match": _gold_blocked(cid, gold) == blocked})
            tp += len(caught)
            fp += len(spurious)
            fn += len(missed)
            vmatch += row["verdict_match"]
            n_lab += 1
            for f in caught:
                by_flag.setdefault(f, {"tp": 0, "fp": 0, "fn": 0})["tp"] += 1
            for f in spurious:
                by_flag.setdefault(f, {"tp": 0, "fp": 0, "fn": 0})["fp"] += 1
            for f in missed:
                by_flag.setdefault(f, {"tp": 0, "fp": 0, "fn": 0})["fn"] += 1
        cases.append(row)
    prec = tp / (tp + fp) if (tp + fp) else None
    rec = tp / (tp + fn) if (tp + fn) else None
    # FINDING-UNITS-1 dual-report: the span-cluster unit score NEXT TO the strict flag score
    # (never replacing it). A unit is TP if gold intersects its code-set — the twin-attribution
    # FP artifact vanishes; a wrong cluster still counts exactly one FP. Labeled rows only.
    units_score = score_units(
        {r["case_id"]: r.get("units") or [] for r in rows
         if r.get("case_id") in labeled and not r.get("error")},
        {r["case_id"]: golds.get(r["case_id"], set()) for r in rows
         if r.get("case_id") in labeled and not r.get("error")},
        code_families=code_families,
    )

    # ── R3a: per-reviewer accuracy + the cross-model majority + the case×reviewer matrix ──
    by_judge: dict[str, dict] = {}
    majority_tally = {"n": 0, "matches_gold": 0, "misses": 0, "over_flags": 0, "ties": 0}
    judge_matrix: list[dict] = []
    # ── R3b: floor tallies + pre/post-floor verdict accuracy (from the SAME rows) ──
    floor_counts = {"cleared": 0, "enforced": 0, "inconclusive": 0}
    gold_defect_clears: list[dict] = []
    pre_match = post_match = pre_n = 0
    # READ-ATTRIB-1: the counterfactual tally rides its own denominator — a cohort with any
    # pre-READ-ATTRIB-1 row reports no counterfactual at all rather than a partial one.
    nofloor_match = nofloor_n = 0
    for r in rows:
        cid = r.get("case_id")
        if not cid or r.get("error"):
            continue
        lab = cid in labeled
        gold_blocked = _gold_blocked(cid, golds.get(cid, set())) if lab else None
        votes = r.get("votes") or []
        cells: list[dict] = []
        n_block = n_pass = 0
        for v in votes:
            role = str(v.get("judge_role") or "judge")
            vote = str(v.get("vote") or "")
            cells.append({"judge_role": role, "model": v.get("model"),
                          "vote": vote, "scores_raw": v.get("scores_raw")})
            v_blocked = _is_blocked_verdict(vote)
            n_block += v_blocked
            n_pass += vote.upper() in ("PASS", "APPROVE")
            if lab:
                j = by_judge.setdefault(role, {
                    "judge_role": role, "model": v.get("model"),
                    "n": 0, "matches_gold": 0, "misses": 0, "over_flags": 0,
                })
                j["n"] += 1
                if v_blocked == gold_blocked:
                    j["matches_gold"] += 1
                elif gold_blocked:
                    j["misses"] += 1  # a silent miss: gold says block, the reviewer passed
                else:
                    j["over_flags"] += 1  # gold says pass, the reviewer blocked
        majority = (
            ("BLOCK" if n_block > n_pass else "PASS" if n_pass > n_block else "TIE")
            if votes else None
        )
        if votes:
            judge_matrix.append({
                "case_id": cid, "verdict": r.get("verdict"),
                "gold": None if gold_blocked is None else ("BLOCK" if gold_blocked else "PASS"),
                "cells": cells, "majority": majority,
            })
        if votes and lab:
            majority_tally["n"] += 1
            if majority == "TIE":
                majority_tally["ties"] += 1  # a tie is reported, never spun as a match
            elif (majority == "BLOCK") == gold_blocked:
                majority_tally["matches_gold"] += 1
            elif gold_blocked:
                majority_tally["misses"] += 1
            else:
                majority_tally["over_flags"] += 1
        fl = r.get("floor") or {}
        floor_counts["cleared"] += len(fl.get("cleared") or [])
        floor_counts["enforced"] += len(fl.get("enforced") or [])
        floor_counts["inconclusive"] += len(fl.get("inconclusive") or [])
        if lab:
            for code in fl.get("cleared") or []:
                # THE safety property: the floor must never clear a genuine (gold) defect.
                if code in golds.get(cid, set()):
                    gold_defect_clears.append({"case_id": cid, "code": code})
            if r.get("verdict"):
                pre_n += 1
                pre_v = r.get("verdict_pre_floor") or r.get("verdict")
                pre_match += _is_blocked_verdict(pre_v) == gold_blocked
                post_match += _is_blocked_verdict(r.get("verdict")) == gold_blocked
                if r.get("verdict_no_floor"):
                    nofloor_n += 1
                    nofloor_match += _is_blocked_verdict(r["verdict_no_floor"]) == gold_blocked

    return {
        "cases": cases,
        "n_cases": len(rows),
        "n_labeled": n_lab,
        "flag": {"tp": tp, "fp": fp, "fn": fn,
                 "precision": round(prec, 3) if prec is not None else None,
                 "recall": round(rec, 3) if rec is not None else None},
        "units": units_score,
        "verdict_accuracy": f"{vmatch}/{n_lab}" if n_lab else None,
        "by_flag": dict(sorted(by_flag.items())),
        "by_judge": list(by_judge.values()),
        "majority": majority_tally,
        "judge_matrix": judge_matrix,
        "floor": {
            **floor_counts,
            "gold_defect_clears": gold_defect_clears,
            "verdict_accuracy_pre_floor": round(pre_match / pre_n, 3) if pre_n else None,
            "verdict_accuracy_post_floor": round(post_match / pre_n, 3) if pre_n else None,
            # READ-ATTRIB-1: post MINUS this is the floor's honest contribution; post minus
            # PRE mixes in the council-rule-vs-rescore gap and must not be called a floor delta.
            "verdict_accuracy_no_floor": (
                round(nofloor_match / nofloor_n, 3) if nofloor_n == pre_n and pre_n else None
            ),
        },
    }


@app.post("/v1/cases/grade")
def grade_cases_endpoint(
    req: GradeCasesRequest,
    db_path: Path = Depends(get_config_db),
    out_dir: Path | None = Depends(get_out_dir),
    workdir: Path = Depends(get_ontology_workdir),
    collections_db: Path = Depends(get_collections_db),
) -> dict:
    """NARR-LOOP — grade the ingested corpus (or a ``case_ids`` subset) and return the cohort
    MATRIX: the "evaluate all of them → report" half of the ingest→grade loop. Each case grades
    through the SAME ``_grade_case`` path as POST /v1/run-eval (so the case_id override, the
    pack-subprocess routing, calibration, and council votes are identical). A per-case grade
    failure is trapped into the row (``error``) so one bad case never aborts the batch."""
    targets = req.case_ids or [
        r["case_id"] for r in _read_ingested_corpus() if r.get("case_id")
    ]
    if not targets:
        raise HTTPException(
            status_code=400,
            detail="no ingested cases to grade (ingest via chat or POST /v1/connector/ingest first)",
        )
    live, in_process = _resolve_run_backend(req)
    # FINDING-UNITS-1: the agent's ontology-declared consolidation families, resolved ONCE for
    # the batch (the clerk clusters by the same ontology the council voted with; {} → inert).
    code_families = _agent_code_families(_load_agent(req.agent, db_path), workdir)
    rows: list[dict] = []
    for cid in targets:
        try:
            rec = _grade_case(
                agent_name=req.agent, case_id=cid, live=live, in_process=in_process,
                db_path=db_path, out_dir=out_dir, workdir=workdir, collections_db=collections_db,
                strict=req.strict,
            )
            comp = rec.get("composite") or {}
            # FINDING-UNITS-1: consolidate the post-floor findings into span-cluster units
            # (one defect span = one unit carrying its full code-set). Gold-blind clerk, not a
            # critic — see harness/finding_units.py; scored dual-report in _cohort_scorecard.
            active = [
                (x.get("code") or x.get("flag_code"))
                for x in (rec.get("grounded") or {}).get("active", [])
            ] or (comp.get("active_findings") or [])
            evidence = ((rec.get("result") or {}).get("semantic") or {}).get("evidence") or []
            units = consolidate(active, evidence, code_families)
            g = rec.get("grounded") or {}
            rows.append(
                {
                    "case_id": cid,
                    "verdict": comp.get("verdict"),
                    "stage_verdict": comp.get("stage_verdict"),
                    "findings": comp.get("active_findings") or [],
                    "units": [list(u.codes) for u in units],
                    # R3: model + raw K-split ride each vote (the per-reviewer scorecard +
                    # the case×reviewer matrix aggregate these in _cohort_scorecard).
                    "votes": [
                        {"judge_role": v.get("judge_role"), "vote": v.get("vote"),
                         "confidence": v.get("confidence"), "model": v.get("model"),
                         "scores_raw": v.get("scores_raw")}
                        for v in (rec.get("council") or {}).get("votes", [])
                    ],
                    # R3b: the pre-floor verdict + the floor events, from the same record.
                    "verdict_pre_floor": g.get("original_verdict") or comp.get("verdict"),
                    # READ-ATTRIB-1: the floor counterfactual (same rescore rule as ``verdict``).
                    # Absent on records graded before READ-ATTRIB-1 — stays None, never faked.
                    "verdict_no_floor": g.get("verdict_no_floor"),
                    "floor": {
                        "cleared": [s.get("code") for s in g.get("suppressed") or []],
                        "enforced": [b.get("flag") for b in g.get("floor_blocks") or []
                                     if b.get("injected")],
                        "inconclusive": [b.get("flag") or b.get("contract_type")
                                         for b in g.get("floor_blocks") or []
                                         if not b.get("injected")],
                    },
                    # CACHE-TRAP-2: per-case replay tell, so one silently-cached case in a batch
                    # is visible instead of averaging invisibly into the cohort numbers.
                    "cache_replay": bool(rec.get("cache_replay")),
                    "run_id": rec.get("pipeline_run_id"),
                }
            )
        except HTTPException as exc:
            rows.append({"case_id": cid, "error": str(exc.detail)})
        except Exception as exc:  # noqa: BLE001 — a batch must never abort on one bad case;
            rows.append({"case_id": cid, "error": str(exc)})  # the failure rides the row, visibly
    graded = [r for r in rows if r.get("verdict")]
    verdicts: dict[str, int] = {}
    for r in graded:
        verdicts[r["verdict"]] = verdicts.get(r["verdict"], 0) + 1
    summary = {
        "n": len(targets),
        "graded": len(graded),
        "errors": len(rows) - len(graded),
        "verdicts": verdicts,
        "grade_path": "live" if live else ("in_process" if in_process else "replay"),
        # CACHE-TRAP-2: how many of these cases spent nothing despite being asked to run live.
        # Non-zero means the batch is NOT an independent measurement and must not be quoted.
        "cache_replays": sum(1 for r in rows if r.get("cache_replay")),
    }
    # RUN-ALL-1: the consolidated report — score the matrix against each case's gold (in-process,
    # no span-matching; case_id rides every row). Labeled cases only feed accuracy (honest-unlabeled).
    # The raw envelope carries no `labeled` key — derive it (gold) the SAME way /v1/cases does.
    # LAYER3-DESCOPE-1: filter gold to the agent's gradeable codes (descoped axes leave the
    # denominator) + credit family-siblings at unit level — both from the same resolved ontology.
    _agent = _load_agent(req.agent, db_path)
    gradeable = _agent_gradeable_codes(_agent, workdir)
    _corpus = _read_ingested_corpus()
    golds, labeled = _corpus_golds_labeled(_corpus, gradeable=gradeable)
    scorecard = _cohort_scorecard(
        rows, golds, labeled, code_families=code_families,
        # R3: a declared expected_compliance_verdict is the gold verdict (the verdict-only-label
        # corpus scores honestly); flags-only labels keep the bool(gold) derivation.
        gold_verdicts=_corpus_gold_verdicts(_corpus),
    )
    return {"matrix": rows, "summary": summary, "scorecard": scorecard}


class EvalPackRunRequest(BaseModel):
    pack_id: str
    agents: list[str] = [DEFAULT_AGENT]
    live: bool = False  # :8002 backend council (HTTP, paid) — replay ($0) by default


@app.post("/v1/eval-pack/run")
def eval_pack_run_endpoint(
    req: EvalPackRunRequest,
    db_path: Path = Depends(get_config_db),
    out_dir: Path | None = Depends(get_out_dir),
    collections_db: Path = Depends(get_collections_db),
    workdir: Path = Depends(get_ontology_workdir),
) -> dict:
    """Batch a pack of agents through the canonical grade and freeze a thin eval-pack
    (R6 — the "did it move the number?" loop). Runs each agent via
    ``evalpack.build_pack`` over ``run_eval.run``; replay (``live=false``) is the $0
    default, ``live=true`` opts into one paid ``:8002`` call per agent. Each run's
    provenance persists to the run-history DB, so the returned outcomes' run ids
    round-trip to ``GET /v1/runs`` + ``GET /v1/runs/{id}/audit``.

    Batch scope this cycle = replay/live (the ``build_pack`` primitive has no
    in_process param); a batched in_process path is a follow-on.
    """
    agents = [_load_agent(name, db_path) for name in req.agents]
    # PACK-WS (same routing as POST /v1/run-eval): a non-_core workspace grades EACH agent in a
    # SUBPROCESS bound to its pack — the in-process _core BFF lacks the pack's grounding executors
    # (e.g. healthcare's snomed_subsumption), which otherwise raises "no executor registered for
    # contract_type 'snomed_subsumption'" mid-batch. The default _core path stays in-process.
    ws = workspace.get_active_workspace()
    grade_fn = None
    if ws.packs_dir or ws.pack != workspace.DEFAULT_PACK:

        def grade_fn(agent, *, live=False, in_process=False, **_kw):
            ontology_path, _src = _resolve_ontology_path(agent, workdir)
            return _grade_via_subprocess(
                agent_name=agent.name, config_db=db_path, ontology_path=ontology_path,
                collections_db=collections_db, out_dir=out_dir, live=live,
                in_process=in_process, ws=ws,
            )

    try:
        pack = evalpack.build_pack(
            req.pack_id,
            agents,
            live=req.live,
            out_dir=out_dir,
            collections_db=collections_db,
            grade_fn=grade_fn,
        )
    except SystemExit as exc:  # a missing case bubbles up as SystemExit from run_eval
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    run_ids = [o.get("pipeline_run_id") for o in pack["outcomes"]]
    return {"pack": pack, "run_ids": run_ids}


# ── R1: GET/PUT /v1/agent — assemble + persist an Agent to the config plane ───


@app.get("/v1/agent")
def get_agent_endpoint(
    name: str = DEFAULT_AGENT,
    db_path: Path = Depends(get_config_db),
) -> dict:
    """Load an assembled Agent (judges + ontology + tools + kb) from the config DB.
    404 on unknown, mirroring _load_agent."""
    return agent_to_dict(_load_agent(name, db_path))


# ── PERSIST-2b: the config-object version history (_history read API) ──────────
#
# The "prove what the config WAS" half of the §2B moat. agent/judge are table-backed →
# their _history reads the {agents,judges}_history copy-on-write shadow (versioning.py);
# ontology is file-backed (no table) → its _history projects the immutable config_audit
# ledger's after-snapshots. The why/who change-stream stays at GET /v1/audit.


def _history_404_if_empty(versions: list[dict], what: str) -> dict:
    if not versions:
        raise HTTPException(status_code=404, detail=f"no version history for {what}")
    return {"versions": versions, "current": versions[0]["object"]}


@app.get("/v1/agent/_history")
def agent_history_endpoint(
    name: str = DEFAULT_AGENT, db_path: Path = Depends(get_config_db)
) -> dict:
    """The version timeline of an agent eval-profile (shadow-backed), newest-first."""
    versions = list_versions(db_path, table="agents", id_col="name", id_val=name)
    return _history_404_if_empty(versions, f"agent {name!r}")


@app.get("/v1/agent/_history/{version}")
def agent_version_endpoint(
    version: int, name: str = DEFAULT_AGENT, db_path: Path = Depends(get_config_db)
) -> dict:
    """The agent eval-profile object as of a specific version."""
    obj = version_at(db_path, table="agents", id_col="name", id_val=name, version=version)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"agent {name!r} has no version {version}")
    return {"version": version, "object": obj}


@app.get("/v1/judges/{role}/_history")
def judge_history_endpoint(role: str, db_path: Path = Depends(get_config_db)) -> dict:
    """The version timeline of a judge config (shadow-backed), newest-first."""
    versions = list_versions(db_path, table="judges", id_col="role", id_val=role)
    return _history_404_if_empty(versions, f"judge {role!r}")


@app.get("/v1/judges/{role}/_history/{version}")
def judge_version_endpoint(
    role: str, version: int, db_path: Path = Depends(get_config_db)
) -> dict:
    """The judge config object as of a specific version."""
    obj = version_at(db_path, table="judges", id_col="role", id_val=role, version=version)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"judge {role!r} has no version {version}")
    return {"version": version, "object": obj}


@app.get("/v1/ontology/_history")
def ontology_history_endpoint(
    agent: str = DEFAULT_AGENT, db_path: Path = Depends(get_config_db)
) -> dict:
    """The version timeline of an agent's ontology (ledger-backed: the file-backed object's
    history is the config_audit after-snapshots), newest-first."""
    versions = ledger_history(db_path, target_type="ontology", target_id=agent)
    return _history_404_if_empty(versions, f"ontology for agent {agent!r}")


@app.get("/v1/ontology/_history/{version}")
def ontology_version_endpoint(
    version: int, agent: str = DEFAULT_AGENT, db_path: Path = Depends(get_config_db)
) -> dict:
    """The ontology object as of a specific version (from the ledger projection)."""
    match = [
        v for v in ledger_history(db_path, target_type="ontology", target_id=agent)
        if v["version"] == version
    ]
    if not match:
        raise HTTPException(
            status_code=404, detail=f"ontology for agent {agent!r} has no version {version}"
        )
    return {"version": version, "object": match[0]["object"]}


@app.put("/v1/agent")
def put_agent_endpoint(
    agent: dict = _AGENT_BODY,
    rationale: str = Query("", description="The SME's change reason (the §2B audit 'why')"),
    db_path: Path = Depends(get_config_db),
    default_actor: Actor = Depends(get_actor),
    x_actor: str | None = Header(None, alias="X-Actor"),
) -> dict:
    """Assemble + persist an Agent to the config plane (R1), with an actor-attributed,
    immutable audit record (R0). Validates the body via an ``agent_from_dict`` round-trip
    (422 on malformed, the WS-5d pattern). NEVER writes the committed seed
    ``data/config/agents/*.json`` — only the (non-committed) config DB. The actor is the
    X-Actor header (a real SME) or the dev default; the agent upsert + its audit row are
    one transaction (config.save_agent, N4)."""
    if not db_path.exists():
        seed_config_db(db_path=db_path)
    try:
        ag = agent_from_dict(agent)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"malformed agent: {exc}") from exc
    actor = _resolve_actor(x_actor, default_actor)
    save_agent(
        ag,
        db_path=db_path,
        actor=actor,
        audit_log=AuditLog(db_path=db_path),
        rationale=rationale,
    )
    return {"status": "ok", "name": ag.name, "actor": actor.model_dump()}


class CouncilRosterRequest(BaseModel):
    """REVIEWER-MODE: how many reviewers run for ``agent`` — ``roster`` is a single role
    ("single reviewer") or a multi-role subset; ``None``/``[]`` = the panel (full pack roster).

    ``extra="forbid"``: an omitted ``roster`` MEANS "clear the override", so a misspelled field
    must 422 — silently ignoring it parsed as ``{roster: None}`` and CLEARED the roster."""

    model_config = ConfigDict(extra="forbid")

    agent: str = DEFAULT_AGENT
    roster: list[str] | None = None


@app.post("/v1/council/roster")
def set_council_roster_endpoint(
    body: CouncilRosterRequest,
    rationale: str = Query("reviewer-mode set from Connect AI"),
    db_path: Path = Depends(get_config_db),
    default_actor: Actor = Depends(get_actor),
    x_actor: str | None = Header(None, alias="X-Actor"),
) -> dict:
    """REVIEWER-MODE (single vs multiple reviewers): set how many reviewers grade for ``agent``.
    A single-role ``roster`` runs that one reviewer (the minimal single-judge council — its vote
    drives ``derive_case_outcome`` + the moat's single-judge consensus); ``None``/``[]`` clears
    the override → the panel (the active pack's full production roster). Persists onto
    ``eval_profile.council_config['reviewer_roster']`` via the SAME audited ``save_agent`` path as
    PUT /v1/agent. Each role is validated against the active pack's production roster (422 on an
    unknown reviewer)."""
    from lithrim_bench.harness import pack as _pack_mod

    ws = workspace.get_active_workspace()
    production = list(_pack_mod.pack_production_judges(ws.pack))
    # GENERALIST-1: a roster may name any pack-declared reviewer — the panel (production_judges)
    # OR an opt-in lens role (e.g. a generalist carrying the full-coverage lens) that runs only
    # via an explicit single-reviewer roster, never inflating the default panel.
    selectable = set(production) | set(_pack_mod.pack_lenses(ws.pack))
    roster = [r for r in (body.roster or []) if r]
    unknown = [r for r in roster if r not in selectable]
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"unknown reviewer(s) {unknown} — the {ws.pack!r} pack offers {sorted(selectable)}",
        )
    ag = _load_agent(body.agent, db_path)
    d = agent_to_dict(ag)
    cc = dict(d["eval_profile"].get("council_config") or {})
    if roster:
        cc["reviewer_roster"] = roster
    else:
        cc.pop("reviewer_roster", None)
    d["eval_profile"]["council_config"] = cc
    actor = _resolve_actor(x_actor, default_actor)
    save_agent(
        agent_from_dict(d),
        db_path=db_path,
        actor=actor,
        audit_log=AuditLog(db_path=db_path),
        rationale=rationale,
    )
    selectable = production + sorted(selectable - set(production))
    return {"status": "ok", "agent": ag.name, "reviewer_roster": cc.get("reviewer_roster"), "panel": production, "selectable": selectable}


@app.get("/v1/council/roster")
def get_council_roster_endpoint(
    agent: str = DEFAULT_AGENT,
    db_path: Path = Depends(get_config_db),
) -> dict:
    """REVIEWER-MODE: the current reviewer roster for ``agent`` — ``reviewer_roster`` is the
    single/subset override (``None`` = panel), ``panel`` is the active pack's full production
    roster (the options + the default). $0, no paid knob."""
    from lithrim_bench.harness import pack as _pack_mod

    ws = workspace.get_active_workspace()
    panel = list(_pack_mod.pack_production_judges(ws.pack))
    # GENERALIST-1: the single-reviewer options = the panel + any opt-in lens role (e.g. a
    # generalist carrying the full-coverage lens) that runs ONLY via an explicit single-reviewer
    # roster, never inflating the default panel. The picker lists ``selectable``.
    selectable = panel + sorted(set(_pack_mod.pack_lenses(ws.pack)) - set(panel))
    rr = None
    try:
        ag = _load_agent(agent, db_path)
        rr = (ag.eval_profile.council_config or {}).get("reviewer_roster")
    except Exception:
        pass
    # CE-JUDGE-RECOMMEND-1: a deterministic panel-vs-single-Generalist recommendation from the
    # pack's reviewer structure (the domain proxy) — the UI renders it as guidance, no model call.
    from lithrim_bench.harness.judges import recommend_reviewer_mode

    recommendation = recommend_reviewer_mode(panel, selectable)
    return {
        "agent": agent, "reviewer_roster": rr, "panel": panel,
        "selectable": selectable, "recommendation": recommendation,
    }


# ── PERSIST-CONV: GET/PUT /v1/conversation — the durable chat thread (refresh-safe) ──


@app.get("/v1/conversation")
def get_conversation_endpoint(
    agent: str = DEFAULT_AGENT,
    db_path: Path = Depends(get_config_db),
) -> dict:
    """Load the persisted conversation thread for ``agent`` (PERSIST-CONV). An agent with no
    stored thread returns ``{"thread": []}`` (a clean default, NOT a 404 — a brand-new agent
    simply has no prose yet). $0, no paid knob."""
    return {"agent": agent, "thread": load_conversation(agent, db_path=db_path)}


@app.put("/v1/conversation")
def put_conversation_endpoint(
    body: ConversationRequest = _CONVERSATION_BODY,
    db_path: Path = Depends(get_config_db),
) -> dict:
    """Persist the conversation thread for ``body.agent`` (PERSIST-CONV). A PLAIN upsert (the
    latest thread wins), NOT an audited write — no X-Actor, no audit record (high-frequency
    per-turn UX state). $0, no paid knob."""
    save_conversation(body.agent, body.thread, db_path=db_path)
    return {"ok": True, "agent": body.agent, "n": len(body.thread)}


@app.delete("/v1/conversation")
def delete_conversation_endpoint(
    agent: str = DEFAULT_AGENT,
    db_path: Path = Depends(get_config_db),
) -> dict:
    """Clear the persisted conversation thread for ``agent`` (PERSIST-CONV — the "clear
    conversation" affordance). A PLAIN, idempotent delete (the per-turn UX-state twin of the
    PUT) — no X-Actor, no audit record, NOT a 404 on an absent thread (a brand-new chat's clear
    is a benign no-op). Clears the chat PROSE only; the audited config writes made inside the
    conversation are untouched. $0, no paid knob."""
    removed = delete_conversation(agent, db_path=db_path)
    return {"ok": True, "agent": agent, "removed": removed}


# ── CRUD-1: GET /v1/agents (the rail switcher) + DELETE /v1/agent (guarded) ────


@app.get("/v1/agents")
def list_agents_endpoint(db_path: Path = Depends(get_config_db)) -> dict:
    """List the config-plane agent names (CRUD-1: the shell rail switcher + the
    blank-slate flow). Builds the DB from the committed seeds on first use (mirrors
    _load_agent), so the seeded agents appear before any authoring."""
    if not db_path.exists():
        seed_config_db(db_path=db_path)
    return {"agents": list_agents(db_path=db_path)}


def _committed_template() -> dict:
    return json.loads((REPO_ROOT / "data" / "config" / "agents" / "ws0_default.json").read_text())


def _pack_agent_template(pack: str) -> dict:
    """Synthesize a blank-slate agent BOUND to a pack — its ontology + a first corpus case, so
    a created agent grades that pack's domain (the council binds the pack at grade time). The
    ontology path resolves UNCHECKED (a different pack is active in this process; the codes gate
    fires for real in the grade subprocess that binds this pack)."""
    from lithrim_bench.harness import pack as pack_mod

    ont = pack_mod.pack_ontology_path(pack, check_consistency=False)
    domain = json.loads(ont.read_text()).get("domain", pack)
    ref = f"{domain}/1"
    cases = pack_mod.pack_cases(pack)
    case = next((c for c in cases if c.get("clean_negative")), cases[0] if cases else None)
    dataset = (
        {"case_id": case["case_id"], "source": case["source"], "baseline": None, "mode": "in_process"}
        if case
        else {"case_id": "", "source": "", "baseline": None, "mode": "in_process"}
    )
    return {
        "name": f"{pack}_default",
        "eval_profile": {
            "judges": ["risk_judge", "policy_judge", "faithfulness_judge"],
            "council_config": {"compliance_council_version": "v2", "disposition": "in-process-v2"},
            "ontology_ref": ref,
            "ontology_path": str(ont),
            "tools": [],
            "kb_bindings": {},
            "severity_map_ref": f"ontology:{ref}",
        },
        "dataset": dataset,
    }


@app.get("/v1/agent/template")
def agent_template_endpoint() -> dict:
    """The blank-slate agent template a fresh agent clones from. PACK-AWARE: for a workspace
    pinning a non-_core pack it binds to THAT pack's ontology + a first case (so the agent
    grades the right domain); else the committed ws0_default (_core). Independent of the
    (possibly empty) active workspace DB."""
    pack = workspace.get_active_workspace().pack
    if pack and pack != "_core":
        try:
            return _pack_agent_template(pack)
        except (FileNotFoundError, KeyError, ValueError, OSError):
            pass  # pack not discoverable here / no ontology → fall back to the blank
    return _committed_template()


# ── workspaces: the switchable domain-setup boundary (the multitenancy primitive) ──


class CreateWorkspaceRequest(BaseModel):
    name: str
    pack: str = "_core"
    packs_dir: str | None = None  # override the discovery dir for this workspace's pack (else inherit)
    actor: str = "you@local"
    owner: str | None = None


class SwitchWorkspaceRequest(BaseModel):
    name: str


@app.get("/v1/workspaces")
def list_workspaces_endpoint() -> dict:
    """Every workspace + the active one. Switching a workspace repoints agents / judges /
    flags / audit / runs / ontology AND the pinned domain pack."""
    return workspace.workspaces_public()


@app.post("/v1/workspace")
def switch_workspace_endpoint(req: SwitchWorkspaceRequest) -> dict:
    """Switch the active workspace — all subsequent reads/writes resolve under it."""
    try:
        ws = workspace.set_active_workspace(req.name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"active": ws.name, "workspace": ws.to_public()}


@app.post("/v1/workspaces")
def create_workspace_endpoint(req: CreateWorkspaceRequest) -> dict:
    """Create a workspace — its own EMPTY config DB, runs, ontology, and pinned pack. A
    fresh workspace starts blank ('create your first agent') so its isolation is obvious;
    only the default workspace carries the seeded ws0_default."""
    try:
        ws = workspace.create_workspace(
            req.name, pack=req.pack, actor=req.actor, owner=req.owner,
            packs_dir=req.packs_dir, seed=False,
        )
    except (ValueError, FileExistsError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"workspace": ws.to_public()}


@app.get("/v1/packs")
def list_packs_endpoint() -> dict:
    """The discoverable DOMAIN packs a workspace can pin (tier core|pro, non-fixture) + the
    active workspace's pack. 'Install a pack' = make it discoverable (pip-install the wheel or
    point LITHRIM_BENCH_PACKS_DIR at it — e.g. drop a pack folder into the CE drop-in volume);
    it then appears here for selection. Each pack carries an ``active`` boolean (PACK-DROPIN-1:
    the active workspace's pinned pack) so the UI can show what loaded; the top-level ``active``
    name is retained for back-compat."""
    from lithrim_bench.harness import pack as pack_mod

    active = workspace.get_active_workspace().pack
    packs = [
        {**p, "active": p["id"] == active}
        for p in pack_mod.discover_packs()
        if p["tier"] in ("core", "pro") and p.get("domain") != "fixture"
    ]
    return {"packs": packs, "active": active}


@app.get("/v1/packs/{pack}/cases")
def pack_cases_endpoint(pack: str) -> dict:
    """A pack's by-construction cases — what a workspace's agent can evaluate (case_id, corpus,
    expected_safety_flags, clean_negative). Empty if the pack ships no corpora / isn't discoverable."""
    from lithrim_bench.harness import pack as pack_mod

    try:
        cases = pack_mod.pack_cases(pack)
    except FileNotFoundError:
        cases = []
    return {"pack": pack, "cases": cases}


@app.get("/v1/meta")
def meta_endpoint(
    db_path: Path = Depends(get_config_db),
    collections_db: Path = Depends(get_collections_db),
) -> dict:
    """The live status-bar meta — the ACTUAL state of the active workspace (no demo numbers):
    workspace + pinned pack, agent count, the pack's council size, run count, the core version."""
    from lithrim_bench import __version__
    from lithrim_bench.harness import pack as pack_mod

    ws = workspace.get_active_workspace()
    try:
        judges = len(pack_mod.pack_production_judges(ws.pack))
    except (FileNotFoundError, KeyError, ValueError, OSError):
        judges = 0
    try:
        runs = len(run_coro(provenance_store_for(collections_db).list_all(limit=500)))
    except (OSError, ValueError, KeyError):
        runs = 0
    return {
        "connected": True,
        "workspace": ws.name,
        "pack": ws.pack,
        "agents": len(list_agents(db_path=db_path)),
        "judges": judges,
        "runs": runs,
        "version": __version__,
    }


@app.delete("/v1/agent")
def delete_agent_endpoint(
    name: str = Query(..., description="The agent to delete"),
    rationale: str = Query("", description="The SME's change reason (the §2B audit 'why')"),
    db_path: Path = Depends(get_config_db),
    default_actor: Actor = Depends(get_actor),
    x_actor: str | None = Header(None, alias="X-Actor"),
) -> dict:
    """Delete an agent eval-profile from the config plane (CRUD-1 D2), with an
    actor-attributed immutable audit record (action="delete", R0). GUARDS (422):
    refuse the seed default (``ws0_default`` — the blank-slate baseline) and refuse
    deleting the LAST remaining agent (the config plane stays non-empty). 404 on an
    unknown name. NEVER touches the committed seed JSON; runs/provenance (a separate
    immutable store keyed by run_id) are untouched — a run that referenced a since-
    deleted agent stays valid history."""
    if not db_path.exists():
        seed_config_db(db_path=db_path)
    names = list_agents(db_path=db_path)
    if name not in names:
        raise HTTPException(status_code=404, detail=f"unknown agent {name!r}")
    if name == DEFAULT_AGENT:
        raise HTTPException(
            status_code=422,
            detail=f"refusing to delete the seed default agent {name!r} (the blank-slate baseline)",
        )
    if len(names) <= 1:
        raise HTTPException(
            status_code=422,
            detail=(
                f"refusing to delete the last remaining agent {name!r} "
                "(the config plane must stay non-empty)"
            ),
        )
    actor = _resolve_actor(x_actor, default_actor)
    delete_agent(
        name,
        db_path=db_path,
        actor=actor,
        audit_log=AuditLog(db_path=db_path),
        rationale=rationale,
    )
    return {"status": "deleted", "name": name, "actor": actor.model_dump()}


# ── UAP-2 R2: GET/PUT /v1/judges — author a judge via ontology-assignment ──────


def _active_lens_by_role() -> dict[str, frozenset[str]]:
    """The active workspace's pack per-role lens (``role -> {codes it may assert}``).

    S-BS-154: the offer/gate authority must track the ACTIVE WORKSPACE pack, not the BFF
    *boot* pack. The module-global ``judge_metric.LENS_BY_ROLE`` (imported at :113) resolves
    ONCE at import → the neutral ``_core`` default; under a ``healthcare`` workspace the editor
    would offer ``_core`` codes the healthcare gate rejects (the live ``422 …
    ['INTERNAL_INCONSISTENCY']``). Mirroring ``_active_snapshot_codes`` exactly, this resolves
    the pack PER-REQUEST via the LAZY ``pack`` / ``workspace`` imports, so OFFER and GATE agree.

    Confined to the BFF: it NEVER touches ``judge_metric.LENS_BY_ROLE`` (byte-frozen — it is
    moat-load-bearing as the withstands-gate default lens in ``signals.py``)."""
    from lithrim_bench.harness import pack as pack_mod
    from lithrim_bench.harness import workspace

    return pack_mod.pack_lenses(workspace.get_active_workspace().pack)


def _effective_model(jc, role: str, bindings: dict) -> tuple[str, str, str]:
    """VOTE-MODEL-2: the model a reviewer actually grades on, with its source.

    Precedence: the per-judge BYOC override (``jc.model``, the editable JudgeEditor field) wins;
    else the Provider-Center role binding (the ``role_bindings`` config DB); else empty (the Azure
    deployment default — unbound). Returns ``(model, provider, source)`` where ``source`` is one of
    ``override`` | ``binding`` | ``default`` so the UI can label which it is."""
    override = getattr(jc, "model", "") if jc else ""
    if override:
        return override, "", "override"
    b = (bindings or {}).get(role) or {}
    if b.get("model"):
        return b["model"], b.get("provider") or "", "binding"
    return "", "", "default"


def _judge_summary(role: str, jc, ontology, bindings: dict | None = None) -> dict:
    """Project one judge: role + bound model + the assigned lens + the assignable
    flags (the active pack's lens — the owned+emitted code set, per-flag tier/when_to_use
    from the ontology) + the derived refinement questions (ontology ``questions_for``) +
    the attached validator refs. An unauthored role serves a derived default (empty
    assignment → the seed ``.txt`` base on render; A4 parity).

    S-BS-154: the offered lens is the ACTIVE-WORKSPACE pack's lens (``_active_lens_by_role``),
    not the boot-pack ``LENS_BY_ROLE``, so the editor offers exactly what the gate accepts."""
    lens = sorted(_active_lens_by_role()[role])
    assigned = list(jc.assigned_flags) if jc else []
    available = []
    for code in lens:
        fd = ontology.flag(code)
        available.append(
            {
                "flag": code,
                "tier": (fd.tier if fd else None),
                "when_to_use": (fd.when_to_use if fd else ""),
                "gradeable": (fd.gradeable if fd else False),
                "assigned": code in assigned,
            }
        )
    questions = [
        {"ordinal": q.ordinal, "text": q.text}
        for q in sorted(ontology.questions_for(role), key=lambda q: q.ordinal)
    ]
    eff_model, eff_provider, model_source = _effective_model(
        jc, role, bindings if bindings is not None else _read_role_bindings()
    )
    return {
        "role": role,
        # the editable per-judge BYOC override (unchanged — the JudgeEditor still edits THIS).
        "model": (jc.model if jc else ""),
        # VOTE-MODEL-2: the model the reviewer actually grades on (override → Provider-Center
        # binding → Azure default), so the config surface reflects what the user assigned.
        "effective_model": eff_model,
        "effective_provider": eff_provider,
        "model_source": model_source,
        "assigned_flags": assigned,
        "validator_refs": (list(jc.validator_refs) if jc else []),
        "available_flags": available,
        "available_validators": list(_KNOWN_VALIDATORS),
        "questions": questions,
        "authored": jc is not None,
        # Per-reviewer sampling config (independent-axes model). ``k`` falls back to the per-role
        # default (5/1/3) so the UI can prefill the effective value even when unauthored. getattr
        # keeps partial JudgeConfig stand-ins (tests) working.
        "k": (getattr(jc, "k", None) if jc and getattr(jc, "k", None) is not None
              else _default_judge_samples().get(role)),
        "temperature": _effective_temperature(jc, role),
        "criterion": (getattr(jc, "criterion", "") if jc else ""),
    }


def _default_judge_samples() -> dict[str, int]:
    """The per-role default k map (5/1/3), imported lazily so the BFF stays council-light."""
    from lithrim_bench.runtime.council.judges_dspy import DEFAULT_JUDGE_SAMPLES

    return DEFAULT_JUDGE_SAMPLES


def _effective_temperature(jc, role) -> float:
    """Temperature to PREFILL in the UI: the authored value if set, else the sampling default
    (1.0) for a k>1 reviewer, else 0.0 (k=1 runs deterministically). Keeps the field consistent
    with the editor's hint — never a value that contradicts the stated default."""
    t = getattr(jc, "temperature", None) if jc else None
    if t is not None:
        return t
    from lithrim_bench.runtime.council.sampling import DEFAULT_SAMPLE_TEMPERATURE

    eff_k = (
        getattr(jc, "k", None) if jc and getattr(jc, "k", None) is not None
        else _default_judge_samples().get(role)
    ) or 1
    return DEFAULT_SAMPLE_TEMPERATURE if eff_k > 1 else 0.0


def _validate_judge_assignment(
    role: str, assigned_flags: list[str], validator_refs: list[str]
) -> None:
    """The PUT gate (422 on violation):
    - ``role`` is a known v2 judge role (the active pack's lens / _TIER1_OWNERS authority);
    - **owner↔emit** (CLAUDE.md invariant #4, S-BS-31/42): every assigned flag is in
      the role's active-pack lens (``_active_lens_by_role``, S-BS-154) — the owned-AND-emitted
      code set, owner-consistent vs ``_TIER1_OWNERS`` by the council guard test
      (``test_every_tier1_lens_code_is_owner_resident``). The ontology's
      ``owner_roles`` are NOT the authority — they are stale v1 roles
      (behavior/source_message, no faithfulness_judge) never re-snapshotted to the
      v2 trio (CITATION-DRIFT, logged at close; the seed fix is a deferred seam);
    - **snapshot** (defense + S-BS-12): every assigned flag is in the taxonomy
      snapshot;
    - ``validator_refs`` ⊆ the persisted toolbox (execute-only; never authored here).
    """
    lens_by_role = _active_lens_by_role()
    if role not in lens_by_role:
        raise HTTPException(status_code=404, detail=f"unknown judge role {role!r}")
    lens = lens_by_role[role]
    off_lens = sorted(c for c in assigned_flags if c not in lens)
    if off_lens:
        raise HTTPException(
            status_code=422,
            detail=(
                f"owner↔emit: {role} may only be assigned codes it owns+emits "
                f"{sorted(lens)}; offenders: {off_lens}"
            ),
        )
    snapshot_codes = _active_snapshot_codes()
    off_snapshot = sorted(c for c in assigned_flags if c not in snapshot_codes)
    if off_snapshot:
        _log.error("assigned flags outside taxonomy snapshot: %s", off_snapshot)
        raise HTTPException(
            status_code=422,
            detail="Some checks aren't in this pack's approved list. Choose from the available checks.",
        )
    bad_refs = sorted(r for r in validator_refs if r not in _KNOWN_VALIDATORS)
    if bad_refs:
        available = ", ".join(sorted(_KNOWN_VALIDATORS))
        _log.error("unknown validator refs %s (known: %s)", bad_refs, available)
        raise HTTPException(
            status_code=422,
            detail=f"That fact-check isn't available. Choose one of: {available}.",
        )


@app.get("/v1/judges")
def list_judges_endpoint(
    agent: str = DEFAULT_AGENT,
    db_path: Path = Depends(get_config_db),
    workdir: Path = Depends(get_ontology_workdir),
) -> dict:
    """List the v2 judge trio: each role + bound model + assigned lens + derived
    questions + validator refs. Questions/flag-metadata resolve against the agent's
    ontology (the working-copy draft if a PUT wrote one, else the committed seed),
    so authored flags are reflected. Does NOT render prompts (no [council] pull) —
    the rendered preview is the per-role GET."""
    saved = list_judges(db_path=db_path)
    try:
        ag = _load_agent(agent, db_path)
        ont_path, _src = _resolve_ontology_path(ag, workdir)
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        # JUDGES-EMPTY-WS: an empty/just-created workspace has no default agent to bind, but the
        # saved judge roster still exists (and /v1/meta counts it). Fall back to the active pack's
        # ontology to render the role questions rather than 404 — meta and /v1/judges must agree.
        from lithrim_bench.harness import pack as pack_mod

        pack = workspace.get_active_workspace().pack or "_core"
        ont_path = pack_mod.pack_ontology_path(pack, check_consistency=False)
    ontology = load_ontology(ont_path)
    # S-BS-154: enumerate the ACTIVE-WORKSPACE pack's roles (healthcare's production_judges
    # = the same trio, so this is a no-op for healthcare, but it keeps offer + gate on one
    # source-of-truth). The unknown-role 404 guards resolve the same active-pack roles.
    roles = sorted(_active_lens_by_role())
    bindings = _read_role_bindings()  # one config-DB read; reused across every role's summary
    judges = [_judge_summary(role, saved.get(role), ontology, bindings) for role in roles]
    return {
        "judges": judges,
        "roles": roles,
        "validators": list(_KNOWN_VALIDATORS),
    }


@app.get("/v1/judges/{role}")
def get_judge_endpoint(
    role: str,
    agent: str = DEFAULT_AGENT,
    assigned_flags: str | None = Query(
        None,
        description="CSV flags for a live $0 prompt preview; omit to render the saved/default assignment",
    ),
    db_path: Path = Depends(get_config_db),
    workdir: Path = Depends(get_ontology_workdir),
) -> dict:
    """One judge's full config + the **rendered ``role_key_questions``** the bridge
    will send ($0, no model). ``base_prompt`` is the unassigned render (== the seed
    ``.txt``, A4 parity); ``rendered_prompt`` is the render for the *effective*
    assignment — the ``assigned_flags`` query (the live before/after preview) if
    given, else the saved/default assignment. This is the demonstrable
    assignment→prompt link (A8), exact because it calls the same
    ``render_role_questions`` the council uses."""
    if role not in _active_lens_by_role():  # S-BS-154: the active-pack roles
        raise HTTPException(status_code=404, detail=f"unknown judge role {role!r}")
    saved = load_judge(role, db_path=db_path)
    ag = _load_agent(agent, db_path)
    ont_path, _src = _resolve_ontology_path(ag, workdir)
    ontology = load_ontology(ont_path)
    summary = _judge_summary(role, saved, ontology)
    if assigned_flags is not None:
        effective = [c.strip() for c in assigned_flags.split(",") if c.strip()]
    else:
        effective = summary["assigned_flags"]
    summary["preview_flags"] = effective
    # GENERALIST-1: render the seed prompt against the ACTIVE WORKSPACE's pack, not the in-process
    # boot pack (``_core``). A non-default-pack role (e.g. a clinverdict ``generalist_reviewer``)
    # has no ``.txt`` under ``_core`` → load_role_prompt would FileNotFoundError → a misleading
    # "judge not set up" in the editor/chat. ``pack_prompts_path(ws.pack)`` resolves the real dir.
    from lithrim_bench.harness.pack import pack_prompts_path

    prompts_dir = pack_prompts_path(workspace.get_active_workspace().pack)
    summary["base_prompt"] = render_role_questions(ontology, role, prompts_dir=prompts_dir)
    summary["rendered_prompt"] = render_role_questions(
        ontology, role, assigned_flags=effective, prompts_dir=prompts_dir
    )
    return summary


@app.put("/v1/judges/{role}")
def put_judge_endpoint(
    role: str,
    judge: dict = _JUDGE_BODY,
    rationale: str = Query("", description="The SME's change reason (the §2B audit 'why')"),
    agent: str | None = Query(
        None,
        description="S-BS-153: when given, also roster this judge onto that agent's "
        "eval_profile.judges (idempotent, audited) so authoring it advances the rail",
    ),
    db_path: Path = Depends(get_config_db),
    default_actor: Actor = Depends(get_actor),
    x_actor: str | None = Header(None, alias="X-Actor"),
) -> dict:
    """Author a judge = assign a flag lens + bind a model + attach validator refs
    (R2). Validates owner↔emit + snapshot + validator-refs → **422** on violation
    (``_validate_judge_assignment``); persists to the config-plane ``judges`` store
    with an actor-attributed, immutable audit record (``target.type='judge'``, R0)
    in one transaction (N4). NEVER generates a validator (execute-only) and NEVER
    writes the committed seed. Body = ``{model, assigned_flags[], validator_refs[]}``;
    the role is the path.

    S-BS-153 (roster-add on judge save, user-locked Option A): the per-role lens-config
    store is SEPARATE from the per-agent roster (``eval_profile.judges``, the rail's Judges
    predicate). When ``agent`` is given, after the judge save succeeds, idempotently add this
    ``role`` to THAT agent's roster, persisted via the SAME audited ``put_agent_endpoint`` path
    ``_assemble_agent`` uses (an AuditRecord for the roster change) — so "author a judge → it's
    on this agent → the rail ticks". No-op if already present; ONLY the named agent mutates;
    editing a lens never strips a roster."""
    assigned = list(judge.get("assigned_flags") or [])
    validator_refs = list(judge.get("validator_refs") or [])
    model = judge.get("model", "") or ""
    # Per-reviewer sampling config (independent-axes model): k (completions sampled per grade),
    # temperature, and the one injected criterion sentence. None k/temperature → the per-role
    # default applies at grade time. Validated lightly here (k>=1; 0<=temp<=2).
    raw_k = judge.get("k")
    raw_temp = judge.get("temperature")
    j_k = int(raw_k) if isinstance(raw_k, (int, float)) else None
    j_temp = float(raw_temp) if isinstance(raw_temp, (int, float)) else None
    j_criterion = str(judge.get("criterion") or "").strip()
    if j_k is not None and j_k < 1:
        raise HTTPException(status_code=422, detail="k must be >= 1")
    if j_temp is not None and not (0.0 <= j_temp <= 2.0):
        raise HTTPException(status_code=422, detail="temperature must be in [0, 2]")
    _validate_judge_assignment(role, assigned, validator_refs)
    actor = _resolve_actor(x_actor, default_actor)
    # PROMPT-EDIT-1: an SME may also rewrite the reviewer's base prompt here (UI parity with the
    # create path) — the positioning is no code dependency to change a prompt. Reuses the existing
    # tier:core-gated, last-write-wins ``write_role_prompt``; a licensed (tier:pro) pack's
    # council_roles stay a backend artifact → 422. Audited as its own who/what/why (§2B). Written
    # before the lens save so a locked-pack rejection short-circuits before the judges store mutates.
    role_prompt = judge.get("role_prompt")
    if role_prompt is not None:
        from lithrim_bench.harness import judge_authoring as ja_mod
        from lithrim_bench.harness import workspace as ws_mod

        pack = ws_mod.get_active_workspace().pack
        try:
            ja_mod.write_role_prompt(pack, role, role_prompt)
        except ja_mod.JudgeAuthoringError as exc:  # NonCorePackError / BadRoleId — the pack boundary
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        AuditLog(db_path=db_path).record(
            AuditRecord(
                actor=actor,
                action="edit_role_prompt",
                target=Target(type="judge", id=role),
                why={"rationale": rationale},
                before=None,
                after={"role_prompt": role_prompt},
            )
        )
    jc = JudgeConfig(
        role=role,
        model=model,
        assigned_flags=tuple(assigned),
        validator_refs=tuple(validator_refs),
        temperature=j_temp,
        k=j_k,
        criterion=j_criterion,
    )
    save_judge(
        jc, db_path=db_path, actor=actor, audit_log=AuditLog(db_path=db_path), rationale=rationale
    )
    rostered = False
    if agent:
        # Roster-add via the FROZEN GET/PUT agent ops (mirrors _assemble_agent): read the
        # current agent, idempotently append THIS role, PUT through the audited op. Per S-BS-82,
        # every Query/Header/Depends param goes to put_agent_endpoint explicitly. Only this agent
        # changes; an existing roster entry is preserved (the append is a no-op if present).
        current = get_agent_endpoint(name=agent, db_path=db_path)  # 404 on unknown agent
        judges = list(current["eval_profile"].get("judges") or [])
        if role not in judges:
            judges.append(role)
            current["eval_profile"]["judges"] = judges
            put_agent_endpoint(
                agent=current,
                rationale=rationale,
                db_path=db_path,
                default_actor=actor,
                x_actor=x_actor,
            )
            rostered = True
    return {
        "status": "ok",
        "role": role,
        "actor": actor.model_dump(),
        "assigned_flags": assigned,
        "agent": agent,
        "rostered": rostered,
    }


@app.delete("/v1/judges/{role}")
def delete_judge_endpoint(
    role: str,
    rationale: str = Query("", description="The SME's change reason (the §2B audit 'why')"),
    db_path: Path = Depends(get_config_db),
    default_actor: Actor = Depends(get_actor),
    x_actor: str | None = Header(None, alias="X-Actor"),
) -> dict:
    """Delete a judge's authored config so the role REVERTS to its default lens
    (CRUD-1 D2). The role is fixed by ``LENS_BY_ROLE`` and never disappears — this
    removes only the authored ``JudgeConfig`` binding (reversible, no flag orphaned),
    which is why judge-delete is the agent-exposable half of CRUD. Audited
    (action="delete", R0). **404** on an unknown role; a known-but-already-default role
    is an idempotent **200** (``removed=false``, no audit row — the trail is
    change-only). NEVER writes the committed seed."""
    if role not in LENS_BY_ROLE:
        raise HTTPException(status_code=404, detail=f"unknown judge role {role!r}")
    actor = _resolve_actor(x_actor, default_actor)
    removed = delete_judge(
        role,
        db_path=db_path,
        actor=actor,
        audit_log=AuditLog(db_path=db_path),
        rationale=rationale,
    )
    return {"status": "reverted", "role": role, "removed": removed, "actor": actor.model_dump()}


@app.post("/v1/judges/{role}/optimize")
def optimize_judge_endpoint(
    role: str,
    req: OptimizeRequest,
    out_dir: Path | None = Depends(get_out_dir),
    collections_db: Path = Depends(get_collections_db),
) -> dict:
    """The calibration trainer (R5, UAP-4) — now **IN-CORPUS** (Phase 2): optimize ``role``
    against the bench-accept metric on a calibration split built from THIS workspace's OWN graded
    cases (in-domain, the active pack's taxonomy), then measure the **honest held-out Δ**
    (precision/recall before→after) on the held-out split. Returns ``{role, n_train, n_heldout,
    baseline, optimized, delta, compile_config, split_counts, corpus}`` — a measured Δ, **including
    ≤0**, is the loop-closure; the accept-gate is NEVER loosened to manufacture a win (the
    ``run_optimize`` contract + the WS-6c-DSPy-3b precedent). ``split_counts`` is surfaced so a tiny
    held-out set reads as small-sample, never hidden.

    PAID + PACK-BOUND: the optimize runs in a subprocess under the workspace's pack
    (``_optimize_via_subprocess``) because the frozen council binds its pack at import and the BFF
    boots on the neutral default pack. The route REFUSES (422) without ``confirm=true`` so the
    cost-confirm is explicit (the shell gates it behind an in-DOM modal, S-BS-69); a corpus too
    small to split also comes back as a calm, actionable 422. Coverage-aware demo selection is ON."""
    ws = workspace.get_active_workspace()
    from lithrim_bench.harness import pack as _pack_mod

    if role not in _pack_mod.pack_lenses(ws.pack):  # pack-aware: the subprocess runs under ws.pack
        raise HTTPException(status_code=404, detail=f"unknown judge role {role!r}")
    if not req.confirm:
        raise HTTPException(
            status_code=422,
            detail=(
                "optimize makes PAID Azure calls (a bootstrap compile over the trainset "
                "+ two held-out evals × the judge). Resend with confirm=true only after "
                "an explicit cost check."
            ),
        )
    resolved_out = out_dir if out_dir is not None else (REPO_ROOT / "out" / "bff" / "optimize")
    return _optimize_via_subprocess(
        role=role, ws=ws, collections_db=collections_db, out_dir=resolved_out, limit=req.limit,
        case_ids=req.case_ids,
    )


@app.get("/v1/ontology")
def ontology_endpoint(
    agent: str = DEFAULT_AGENT,
    db_path: Path = Depends(get_config_db),
    workdir: Path = Depends(get_ontology_workdir),
) -> dict:
    """The agent's ontology JSON. Prefers a working copy a prior PUT wrote (so a
    PUT then GET round-trips); else the committed seed (the same 'stored ontology'
    the live council is sent at run_eval.py:142). Shares ``_resolve_ontology_path``
    with POST /v1/run-eval so read + grade resolve to the same file (R3)."""
    ag = _load_agent(agent, db_path)
    path, _source = _resolve_ontology_path(ag, workdir)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"ontology not found: {path}")
    return json.loads(path.read_text())


@app.get("/v1/agents/{agent}/readiness")
def agent_readiness_endpoint(
    agent: str,
    db_path: Path = Depends(get_config_db),
    workdir: Path = Depends(get_ontology_workdir),
) -> dict:
    """The agent↔pack READINESS preflight (setup-time, ``$0``): does this agent's RESOLVED ontology
    carry every verification-contract the pinned pack declares — each with a registered executor and
    a permitted tool — plus a floor for every raiseable high-stakes fabrication code?

    A pure, offline read (``harness.readiness``) — no grade, no LLM. It surfaces the silent hole the
    council-lens-vs-agent-ontology split creates: a pack-declared floor that would never fire because
    the graded (agent) ontology lacks its contract. ``ok: false`` + per-check ``findings`` (ERROR /
    WARN, with a one-line remediation each) the shell renders inline as a setup-gaps card. Shares
    ``_resolve_ontology_path`` with the grade so the preflight assesses exactly the ontology that
    would grade. ``assessed: false`` when the pack isn't discoverable here (soft, never a false OK)."""
    ag = _load_agent(agent, db_path)
    path, source = _resolve_ontology_path(ag, workdir)
    pack = workspace.get_active_workspace().pack
    report = _compute_readiness(ag, path, source, pack)
    if report is None:
        return {
            "ok": True, "pack": pack, "agent": agent, "ontology_source": source,
            "findings": [], "assessed": False,
        }
    out = report.to_dict()
    out["assessed"] = True
    return out


@app.get("/v1/grounding-contract/types")
def grounding_contract_types_endpoint() -> dict:
    """FAUTH-2 (G3): the active WORKSPACE's pack REGISTERED grounding-contract executor keys
    (suppress ∪ floor) — the pack-true list the inline ``ContractBuilder`` drives its type
    selector from, retiring the hand-maintained static constant (S-BS-FAUTH1-1). It is the SAME
    set the author-time gate in ``_put_grounding_contract`` admits, so the UI can only offer a
    type that will actually be accepted (and that ``ground()`` will not raise on at grade time).
    READ-ONLY: it CALLS ``grounding.suppress_executors()`` / ``floor_executors()`` (the moat
    accessors) and writes nothing — no audit, no PUT, $0.

    FAUTH-2a (S-BS-FAUTH2-2, the S-BS-154 family): resolve the ACTIVE WORKSPACE's grade pack
    PER-REQUEST (``workspace.get_active_workspace().pack``), NOT the BFF *process* pack
    (``LITHRIM_BENCH_PACK``, live = ``_core``). A non-``_core`` workspace grades in a subprocess
    bound to ITS pack, so reading the process pack here false-rejected the clinical floors
    (``record_presence``/``snomed_subsumption``/``dosage_grounding``) on a healthcare workspace.
    Mirrors ``_active_lens_by_role`` exactly so OFFER and GATE agree."""
    from lithrim_bench.harness import grounding as _grounding
    from lithrim_bench.harness import workspace as _workspace

    ws_pack = _workspace.get_active_workspace().pack
    registered = set(_grounding.suppress_executors(ws_pack)) | set(_grounding.floor_executors(ws_pack))
    return {"contract_types": sorted(registered), "pack": ws_pack}


def _active_snapshot_codes() -> frozenset[str]:
    """The active workspace's pack KNOWN_TAXONOMY_CODES (the gradeable gate).

    PACK-DIST-2 (C3): delegates to the domain-agnostic
    ``harness.admissibility.active_snapshot_codes`` — the single snapshot-resolution path the
    config-write gate uses (it resolves the ACTIVE WORKSPACE'S pack, not a hardcoded clinical
    path). Kept as a thin local alias for the in-module callers."""
    return admissibility.active_snapshot_codes()


def _validate_ontology(ontology: dict, *, lint_flags: list[dict] | None = None) -> None:
    """The PUT gate: reject malformed or snapshot-violating ontologies (HTTP 422).

    Two checks, both import-only over the harness:
      1. structural round-trip through ``ontology.from_dict`` (the eval-load path) — over the WHOLE
         ontology;
      2. the S-BS-10/12 snapshot lint (``harness.admissibility``) — a ``gradeable`` flag
         outside the active pack's taxonomy snapshot is rejected loudly (the CLAUDE.md core
         invariant: never silently score a flag the contract-of-record has not blessed).

    ``lint_flags`` (S-BS-142) scopes the snapshot lint (check #2) to a SUBSET of flags; ``None``
    (the default) lints ALL flags — the PUT-gate behavior, UNCHANGED. The criterion endpoint passes
    only the NET-NEW flag (which it just spliced into the active snapshot), so a pre-existing flag a
    DIFFERENT pack admitted does not falsely 422 the new criterion. The invariant holds: the new
    code is still gated (the splice + this scoped lint), and a real PUT still lints every flag.
    """
    try:
        ontology_from_dict(ontology)
    except (KeyError, TypeError, ValueError) as exc:
        _log.error("malformed ontology: %s", exc)
        raise HTTPException(
            status_code=422, detail="We couldn't read your checklist. Please try again."
        ) from exc
    flags_to_lint = (ontology.get("flags") or []) if lint_flags is None else lint_flags
    offenders = admissibility.gradeable_flags_outside_snapshot(
        flags_to_lint, _active_snapshot_codes()
    )
    if offenders:
        raise HTTPException(status_code=422, detail=_gradeable_offender_detail(offenders))


def _gradeable_offender_detail(offenders: list[str]) -> str:
    """The 422 message for a gradeable flag outside the snapshot — TIER-AWARE (NARR-5-CRIT).

    The gate is unchanged (labels true by construction); only the GUIDANCE is corrected. For a
    ``tier:core`` pack (a hand-authored domain) the fix is the sanctioned self-serve writer
    (``create_gradeable_criterion`` / POST ``/v1/criterion``), NOT the clinical backend re-snapshot
    the old message misdirected the SME toward. For a ``tier:pro`` pack (a backend-derived snapshot)
    the re-snapshot guidance stands."""
    tier = "core"
    try:
        from lithrim_bench.harness import pack as _pack_mod
        from lithrim_bench.harness import workspace as _ws

        tier = _pack_mod._manifest(_ws.get_active_workspace().pack).get("tier", "core")
    except Exception:  # noqa: BLE001 - resolution failure → safest (core) guidance
        tier = "core"
    if tier == "core":
        return (
            "a gradeable flag must first be minted into the active pack's taxonomy snapshot via the "
            "sanctioned self-serve writer (create_gradeable_criterion / POST /v1/criterion) — a PUT "
            "/v1/ontology alone cannot create one (labels are true by construction). "
            f"Offending gradeable codes: {offenders}"
        )
    return (
        "a gradeable flag requires a lithrim-backend re-snapshot "
        "(scripts/snapshot_taxonomy.py --backend-path …); it cannot be created from clean "
        "locally — labels are true by construction. See docs/ONTOLOGY_FLAG_LIFECYCLE.md. "
        f"Offending gradeable codes: {offenders}"
    )


@app.put("/v1/ontology")
def put_ontology_endpoint(
    ontology: dict = _ONTOLOGY_BODY,
    agent: str = DEFAULT_AGENT,
    rationale: str = Query("", description="The SME's change reason (the §2B audit 'why')"),
    db_path: Path = Depends(get_config_db),
    workdir: Path = Depends(get_ontology_workdir),
    default_actor: Actor = Depends(get_actor),
    x_actor: str | None = Header(None, alias="X-Actor"),
) -> dict:
    """Validate + persist an edited ontology to a non-committed working copy (WS-5d) +
    emit an actor-attributed, immutable audit record (R0 — audit across all config
    writes).

    Clobber-safe by construction: the write target is ``workdir/<agent>.json``, never
    the committed seed. Validation (``_validate_ontology``) rejects malformed or
    snapshot-violating bodies with 422 before anything lands. The audit record carries
    the canonical before (the prior served ontology — working copy if one exists, else
    the committed seed) → after (the new body) diff + why={rationale}.
    """
    _validate_ontology(ontology)
    ag = _load_agent(agent, db_path)
    before_path, _src = _resolve_ontology_path(ag, workdir)
    before = json.loads(before_path.read_text()) if before_path.exists() else None
    workdir.mkdir(parents=True, exist_ok=True)
    path = workdir / f"{agent}.json"
    path.write_text(json.dumps(ontology, indent=2, sort_keys=True))
    actor = _resolve_actor(x_actor, default_actor)
    AuditLog(db_path=db_path).record(
        AuditRecord(
            actor=actor,
            action="edit",
            target=Target(type="ontology", id=agent),
            why={"rationale": rationale},
            before=before,
            after=ontology,
        )
    )
    return {"status": "ok", "agent": agent, "working_copy": str(path)}


class CriterionRequest(BaseModel):
    # F1: a taxonomy code is an uppercase-led SCREAMING_SNAKE token — refuse garbage at the boundary
    # (the writer ALSO guards, defense-in-depth) so nothing malformed reaches the contract-of-record.
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    tier: str  # TIER_1 | TIER_2 | TIER_3 (or T1/T2/T3 / the long snapshot tier-set names)
    owner_role: str  # must be a production judge of the active pack
    category: str = "completeness"
    definition: str = ""
    when_to_use: str = ""
    when_NOT_to_use: str = ""


@app.post("/v1/criterion")
def create_criterion_endpoint(
    body: CriterionRequest,
    agent: str = DEFAULT_AGENT,
    rationale: str = Query("", description="The SME's change reason (the §2B audit 'why')"),
    db_path: Path = Depends(get_config_db),
    workdir: Path = Depends(get_ontology_workdir),
    default_actor: Actor = Depends(get_actor),
    x_actor: str | None = Header(None, alias="X-Actor"),
) -> dict:
    """NARR-5-CRIT: mint a new GRADEABLE criterion self-serve — the sanctioned, AUDITED writer
    above the CLAUDE.md "never hand-edit the snapshot" invariant (owner sign-off 2026-06-21).

    Splices the code into the active WORKSPACE pack's taxonomy snapshot (``tiers`` + ``lenses`` +
    ``tier1_owners``-when-T1) via the tier:core-gated harness writer, then appends the
    ``gradeable=True`` ontology flag to the agent overlay under the NOW-passing admissibility lint —
    ONE audited action, atomic (the snapshot is rolled back if the ontology write fails). The gate
    itself is unchanged; this is the admissible self-serve path INTO it, not a weakening.

    422 on a non-core pack / unknown owner / bad tier; 409 on a duplicate code.
    """
    from lithrim_bench.harness import criterion as crit_mod
    from lithrim_bench.harness import workspace as ws_mod

    pack = ws_mod.get_active_workspace().pack
    try:
        snap_before, snap_after = crit_mod.splice_gradeable_criterion(
            pack, body.code, body.tier, body.owner_role
        )
    except crit_mod.DuplicateCriterionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except crit_mod.CriterionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Post-splice writes: the ontology overlay AND the audit, under the now-passing lint. ATOMIC —
    # on ANY failure (validation, overlay write, OR the audit, F2) roll BOTH the snapshot AND the
    # overlay back so the snapshot/ontology never diverge and no un-audited snapshot mutation lands.
    workdir.mkdir(parents=True, exist_ok=True)
    out_path = workdir / f"{agent}.json"
    overlay_before = out_path.read_text() if out_path.exists() else None
    try:
        ag = _load_agent(agent, db_path)
        before_path, _src = _resolve_ontology_path(ag, workdir)
        ontology = (
            json.loads(before_path.read_text())
            if before_path.exists()
            else {"flags": [], "questions": [], "verification_contracts": []}
        )
        new_flag = {
            "flag": body.code,
            "category": body.category,
            "definition": body.definition,
            "when_to_use": body.when_to_use,
            "when_NOT_to_use": body.when_NOT_to_use,
            "owner_roles": [body.owner_role],
            "tier": crit_mod.short_tier_name(body.tier),
            "gradeable": True,
        }
        new_ontology = {**ontology, "flags": [*(ontology.get("flags") or []), new_flag]}
        # S-BS-142: lint ONLY the net-new code (the splice just blessed it). Re-linting the WHOLE
        # ontology falsely 422'd the new criterion when a PRE-EXISTING flag was admitted under a
        # different pack (out of THIS pack's snapshot). The structural round-trip still covers the
        # whole ontology; atomicity (rollback on any post-splice failure) is unchanged.
        _validate_ontology(new_ontology, lint_flags=[new_flag])
        out_path.write_text(json.dumps(new_ontology, indent=2, sort_keys=True))
        actor = _resolve_actor(x_actor, default_actor)
        # F3: the audit captures the FULL governance delta — tiers + lenses (raise authority) +
        # tier1_owners (the T1 one-strike), not only `tiers`.
        AuditLog(db_path=db_path).record(
            AuditRecord(
                actor=actor,
                action="create",
                target=Target(type="criterion", id=body.code),
                why={
                    "rationale": rationale,
                    "tier": body.tier,
                    "owner_role": body.owner_role,
                    "pack": pack,
                },
                before={
                    "tiers": snap_before["tiers"],
                    "lenses": snap_before["lenses"],
                    "tier1_owners": snap_before.get("tier1_owners", {}),
                },
                after={
                    "tiers": snap_after["tiers"],
                    "lenses": snap_after["lenses"],
                    "tier1_owners": snap_after.get("tier1_owners", {}),
                    "ontology_flag": new_flag,
                },
            )
        )
    except Exception:
        crit_mod.restore_snapshot(pack, snap_before)
        if overlay_before is not None:
            out_path.write_text(overlay_before)
        elif out_path.exists():
            out_path.unlink()
        raise

    return {
        "status": "ok",
        "code": body.code,
        "tier": crit_mod.short_tier_name(body.tier),
        "owner_role": body.owner_role,
        "pack": pack,
        "working_copy": str(out_path),
    }


class CreateJudgeRequest(BaseModel):
    # PHASE2-B: author a NEW production judge self-serve. ``role`` is a lowercase-led snake judge-id
    # (the writer ALSO guards, defense-in-depth). ``lens_codes`` = the codes it may raise (its lens /
    # withstands scope, non-empty); ``owned_codes`` ⊆ lens_codes = the Tier-1 one-strike codes it
    # OWNS (owner↔emit). ``model_id`` (optional) binds a registered pool model to the role.
    role: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    lens_codes: list[str]
    owned_codes: list[str] = Field(default_factory=list)
    model_id: str | None = None
    role_prompt: str | None = None


def _bind_model_to_role(model_id: str, role: str) -> dict:
    """Bind a registered pool model to an ARBITRARY (incl. authored) role, REUSING the
    ``models_bind_endpoint`` internals (``_read_models_registry`` → ``_read_model_key`` →
    ``_provider_env_vars`` → ``_persist_and_reload_provider``) — NOT duplicated. The global
    provider + key are set (the load-bearing part: ``build_judge_lm`` then routes the new role to
    that provider via its ``.get(role, default)`` fallback, PROBE Q6). A per-role MODEL var for an
    arbitrary new role is the flagged 3→N seam (``_PROVIDER_*_ROLE_*`` are the fixed trio); honored
    only when ``role`` is one of the three. Records ``bound_roles += [role]``. NEVER returns a key."""
    reg = _read_models_registry()
    entry = next((m for m in reg["models"] if m.get("id") == model_id), None)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"model {model_id!r} not in the pool")
    api_key = _read_model_key(model_id)
    if not api_key:
        raise HTTPException(
            status_code=409, detail=f"model {model_id!r} has no persisted key (re-register it)"
        )
    # role-targeted only for the fixed trio (the per-role env-var maps); else a global provider+key
    # bind (no per-role model clobber) — the new role runs on the bound provider's default model.
    targeted = role in _PROVIDER_OPENAI_ROLE_MODEL
    cfg = ProviderConfigRequest(
        plane="grading", provider=entry["provider"], api_key=api_key,
        endpoint=entry.get("endpoint"), model=entry.get("model") if targeted else None,
        role=role if targeted else None,
    )
    try:
        env_vars = _provider_env_vars(cfg)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _persist_and_reload_provider(env_vars)
    bound = sorted(set(entry.get("bound_roles", [])) | {role})
    entry["bound_roles"] = bound
    _write_models_registry(reg)
    # NEVER the key — only the non-secret binding facts
    return {"id": model_id, "provider": entry["provider"], "model": entry.get("model"),
            "bound_roles": bound}


@app.post("/v1/judges")
def create_judge_endpoint(
    body: CreateJudgeRequest,
    rationale: str = Query("", description="The SME's change reason (the §2B audit 'why')"),
    db_path: Path = Depends(get_config_db),
    default_actor: Actor = Depends(get_actor),
    x_actor: str | None = Header(None, alias="X-Actor"),
) -> dict:
    """PHASE2-B: author a NEW production judge self-serve — the sanctioned, AUDITED writer above
    the CLAUDE.md "never hand-edit the snapshot" invariant (owner sign-off 2026-06-25, after the
    ``docs/research/PROBE_phase2_arbitrary_judges_2026-06-25.md`` §8 gate: the FROZEN consensus
    admits arbitrary judges at N≥2). The STRUCTURAL TWIN of ``POST /v1/criterion``.

    Splices the role into the active WORKSPACE pack's taxonomy snapshot — ``production_judges``
    (roster identity) + ``lenses[role]`` (withstands scope) + ``tier1_owners`` (the one-strike
    owner-map, for owned codes) — via the tier:core-gated harness writer, seeds the role prompt,
    optionally binds a registered pool model to the role, and persists a ``JudgeConfig`` — ONE
    audited action, atomic (the snapshot is rolled back on any later failure). The frozen council
    (``_apply_consensus``) is UNTOUCHED — it resolves the spliced roster/lens/owner at runtime and
    grades the larger council with no engine edit.

    Body = ``{role, lens_codes[], owned_codes[]=[], model_id?, role_prompt?}``. Maps the writer's
    admissibility rejections to HTTP: non-core pack / bad role-id / empty lens / unknown code /
    inert owner (owned⊄lens) → 422; role collision → 409. NEVER leaks a model key.
    """
    from lithrim_bench.harness import judge_authoring as ja_mod
    from lithrim_bench.harness import workspace as ws_mod

    pack = ws_mod.get_active_workspace().pack
    try:
        snap_before, _snap_after = ja_mod.splice_production_judge(
            pack, body.role, body.lens_codes, body.owned_codes
        )
    except ja_mod.RoleCollisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ja_mod.JudgeAuthoringError as exc:  # NonCorePack/BadRoleId/EmptyLens/UnknownCode/InertOwner
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Post-splice writes: the role prompt, the optional model bind, the JudgeConfig + its audit.
    # ATOMIC — on ANY failure (incl. the model bind 404/409, or the audit, F2) roll the snapshot
    # back AND remove the seeded prompt so no un-audited mutation of the contract-of-record lands.
    # The save_judge audit (action="author", target.type="judge") is the SOLE audit (one action).
    from lithrim_bench.harness import pack as _pack_mod_w

    prompt_path = _pack_mod_w._pack_ref(pack, "council_roles") / f"{body.role}.txt"
    prompt_existed = prompt_path.exists()
    bound = None
    try:
        ja_mod.write_role_prompt(
            pack,
            body.role,
            body.role_prompt
            or f"{body.role}: raise only its assigned lens, each grounded in an evidence span.",
        )
        if body.model_id:
            bound = _bind_model_to_role(body.model_id, body.role)
        actor = _resolve_actor(x_actor, default_actor)
        jc = JudgeConfig(
            role=body.role,
            model=(bound or {}).get("model", "") or "",
            assigned_flags=tuple(body.lens_codes),
            validator_refs=(),
        )
        save_judge(
            jc, db_path=db_path, actor=actor, audit_log=AuditLog(db_path=db_path), rationale=rationale
        )
    except Exception:  # HTTPException is an Exception — one rollback for every failure
        ja_mod.restore_snapshot(pack, snap_before)
        if not prompt_existed and prompt_path.exists():
            prompt_path.unlink()
        raise

    return {
        "role": body.role,
        "lens_codes": list(body.lens_codes),
        "owned_codes": list(body.owned_codes),
        "model": (bound or {}).get("model"),  # never a key
        "bound_roles": (bound or {}).get("bound_roles", []),
        "pack": pack,
        "actor": actor.model_dump(),
        "audit_id": f"judge:{body.role}",
    }


def _pin_arguments_jute(params: dict) -> dict:
    """CRITERION-JUTE-1a authoring-side pin-write: when a contract declares ``arguments_jute`` (the
    pinned per-case JUTE arg-mapping) but no ``arguments_jute_sha256``, compute + store the sha256 so
    the authored mapping is PINNED — the grade-time executor hash-verifies against it and refuses a
    drifted transform. A caller-supplied sha256 is trusted as-is (the caller may pin explicitly). No
    ``arguments_jute`` -> params returned unchanged (byte-identical for every existing contract)."""
    jute = params.get("arguments_jute")
    if not jute or params.get("arguments_jute_sha256"):
        return params
    pinned = dict(params)
    pinned["arguments_jute_sha256"] = hashlib.sha256(jute.encode("utf-8")).hexdigest()
    return pinned


# ── CRITERION-JUTE-1d: the SME tool-grounded criterion loop — generate (1b) → gate (1c) → pin (1a) ──
# The two orchestration steps are MODULE-LEVEL hooks so a networkless test monkeypatches them (an LM +
# :3031 + Hermes are needed live). The endpoint below composes: build the candidate arguments_jute,
# replay the 1c corpus gate, PREVIEW ($0) or PIN-on-pass through the FROZEN put path (422 on fail).
_CRITERION_JUTE_CORPUS_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "subsumption_bidirectional"


def _load_criterion_jute_corpus() -> list[dict]:
    """The bidirectional subsumption corpus the 1c gate replays a candidate contract over (22 upcoded
    positives + 22 clean-generalization negatives + 2 SPAN-BIND analogues). Read from the in-repo
    fixtures; a missing dir yields an empty corpus (the gate then vacuously passes — the endpoint
    guards against an empty corpus so a preview/commit over nothing is a clean 422)."""
    cases: list[dict] = []
    if not _CRITERION_JUTE_CORPUS_DIR.is_dir():
        return cases
    for name in (
        "upcoded_positives.jsonl",
        "clean_generalization_negatives.jsonl",
        "span_bind_positives.jsonl",
    ):
        p = _CRITERION_JUTE_CORPUS_DIR / name
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def _criterion_jute_generate_argshape(
    *,
    flag_code: str,
    tool: str,
    call: str,
    criterion: str,
    sample_case: dict,
    input_schema: dict,
    n_generations: int,
) -> dict:
    """Build the candidate ``arguments_jute`` from the plain-English criterion + the tool call's
    inputSchema over a sample ``{case, finding}`` envelope, via the 1b argshape refine loop
    (``build_argshape_generator`` + ``best_of_n_argshape``, live-gated on :3031). Returns
    ``{arguments_jute, arguments_jute_sha256}``. LIVE: needs :3031 (the JUTE apply gate) + an LM
    (the generator). A networkless test monkeypatches THIS function with a fixed transform, so the
    endpoint's orchestration + gate + pin are exercised offline."""
    from lithrim_bench.verification import (
        EtlpJuteClient,
        best_of_n_argshape,
        build_argshape_generator,
        render_dsl_excerpt,
    )

    client = EtlpJuteClient(base_url=_jute_base_url())
    _health = getattr(client, "health", None)
    if callable(_health) and not _health():
        raise RuntimeError(
            f"the JUTE mapper is not reachable at {getattr(client, 'base', _jute_base_url())} "
            "— criterion-jute generation needs it to live-gate the arg-shaping transform. Start the "
            "bundled mapper (`docker compose up` includes it) or point LITHRIM_JUTE_URL at one."
        )
    # the sample envelope 1a re-applies at grade time: {case, finding}. A finding is the first
    # _synth_findings entry (the SME's sample case), else an empty dict (the gate then rejects).
    findings = (sample_case or {}).get("_synth_findings") or []
    envelope = {"case": sample_case or {}, "finding": findings[0] if findings else {}}
    # the argshape generator authors a JUTE arg-mapping (extractor-style), so ground it on the LIVE
    # DSL spec with the EXTRACTOR addendum — mirroring the _ingest_cases LM-gen path (NARR-7/G1).
    dsl_excerpt = render_dsl_excerpt(
        client.get_dsl_spec(), include_envelope_example=False, for_extractor=True
    )

    def make_gen():
        return build_argshape_generator(
            client, dsl_excerpt, envelope, input_schema=input_schema, criterion=criterion
        )

    pred = best_of_n_argshape(make_gen, criterion, envelope, n=n_generations)
    jute = getattr(pred, "jute_transform", "") or ""
    if not getattr(pred, "accepted", False) or not jute.strip():
        raise RuntimeError(
            "the argshape generator did not converge on a transform satisfying the tool call's "
            f"inputSchema for {tool}.{call} — nothing pinned"
        )
    return {
        "arguments_jute": jute,
        "arguments_jute_sha256": hashlib.sha256(jute.encode("utf-8")).hexdigest(),
    }


def _criterion_jute_gate(candidate_params: dict):
    """Replay ``candidate_params`` (an ``mcp_call`` + ``arguments_jute`` contract) over the
    bidirectional subsumption corpus via the 1c ``gate_contract_over_corpus`` (the REAL frozen
    ``McpCallGrounding`` executor with the corpus-derived oracle + the pinned :3031 transform). LIVE:
    needs Hermes SNOMED (the terminology oracle) + :3031 (the JUTE apply). A networkless test
    monkeypatches THIS function to inject the golden fakes (the disclosed-circularity oracle + a fixed
    jute_apply), exercising the endpoint's gate → preview/pin decision offline. Returns a GateReport."""
    from lithrim_bench.verification import EtlpJuteClient
    from lithrim_bench.verification.argshape_gate import gate_contract_over_corpus
    from lithrim_bench.verification.mcp_client import McpStdioClient

    corpus = _load_criterion_jute_corpus()

    def jute_apply(case: dict, finding: dict) -> dict:
        client = EtlpJuteClient(base_url=_jute_base_url())
        return client.test_template(
            candidate_params.get("arguments_jute", ""), {"case": case, "finding": finding}
        )

    def snomed_oracle(call: str, arguments: dict):
        from lithrim_bench.harness import plugins

        manifest = plugins.resolve_tool(candidate_params.get("tool"))
        mcp = ((manifest.service if manifest else {}) or {}).get("mcp") or {}
        with McpStdioClient(command=mcp.get("command"), args=mcp.get("args", [])) as c:
            return c.call_tool(call, arguments)

    return gate_contract_over_corpus(
        candidate_params, corpus, jute_apply=jute_apply, snomed_oracle=snomed_oracle
    )


def _gate_report_dict(report) -> dict:
    """Project a 1c GateReport into the JSON the preview/commit response + the inline card render."""
    return {
        "negatives_cleared": report.negatives_cleared,
        "negatives_total": report.negatives_total,
        "positives_standing": report.positives_standing,
        "positives_total": report.positives_total,
        "span_bind_ok": report.span_bind_ok,
        "span_bind_cases": report.span_bind_cases,
        "failures": list(report.failures),
        "passed": report.passed,
    }


@app.post("/v1/criterion-jute/generate")
def criterion_jute_generate_endpoint(
    body: CriterionJuteGenerateRequest,
    db_path: Path = Depends(get_config_db),
    out_dir: Path | None = Depends(get_out_dir),
    workdir: Path = Depends(get_ontology_workdir),
    collections_db: Path = Depends(get_collections_db),
    default_actor: Actor = Depends(get_actor),
    x_actor: str | None = Header(None, alias="X-Actor"),
) -> dict:
    """CRITERION-JUTE-1d: the SME tool-grounded criterion authoring loop — generate (1b) → gate (1c) →
    pin (1a). An SME picks a tool+call, a plain-English ``criterion`` seeds generation of the
    ``arguments_jute`` (the pinned per-case JUTE arg-mapping), the bidirectional subsumption corpus
    gate replays the candidate contract, and the ``mcp_call`` + ``arguments_jute`` contract PINS on
    pass. Mirrors ``_ingest_cases`` (the generate→gate→pin front door): ``commit=False`` (the default)
    returns a PREVIEW (the argshape + the gate report; $0, writes NOTHING); ``commit=True`` + a PASSING
    gate pins ONE contract through the SAME frozen ``ctx.put_grounding_contract`` path (so the 404
    unknown-flag / 422 malformed gates + the single audited write hold); a FAILING gate 422s naming the
    failing case ids and pins NOTHING (labels stay true by construction — a contract that mis-clears a
    negative or lets a positive through never enters the store)."""
    # (1) build the candidate arguments_jute (1b). The tool call's inputSchema rides sample_case's
    # _tool_input_schema if the SME provided it (else empty → the generator/gate surface the gap).
    input_schema = (body.sample_case or {}).get("_tool_input_schema") or {}
    gen = _criterion_jute_generate_argshape(
        flag_code=body.flag_code,
        tool=body.tool,
        call=body.call,
        criterion=body.criterion,
        sample_case=body.sample_case or {},
        input_schema=input_schema,
        n_generations=body.n_generations,
    )
    arguments_jute = gen["arguments_jute"]
    arguments_jute_sha256 = gen["arguments_jute_sha256"]

    # (2) the candidate contract params (1a shape) + the 1c corpus gate.
    candidate_params = {
        "tool": body.tool,
        "call": body.call,
        "arguments_jute": arguments_jute,
        "arguments_jute_sha256": arguments_jute_sha256,
        "authority": body.authority,
        "match": body.match,
    }
    report = _criterion_jute_gate(candidate_params)
    gate_report = _gate_report_dict(report)

    # (3) PREVIEW ($0, no write).
    if not body.commit:
        return {
            "status": "preview",
            "arguments_jute": arguments_jute,
            "arguments_jute_sha256": arguments_jute_sha256,
            "gate_report": gate_report,
        }

    # (4/5) COMMIT: a FAILING gate 422s (naming the case ids); a PASSING gate PINS through the frozen
    # put path (the SAME bound op the ContractBuilder route + add_grounding_contract chat tool use).
    if not report.passed:
        raise HTTPException(
            status_code=422,
            detail=(
                "the candidate mcp_call/arguments_jute contract FAILED the bidirectional corpus gate — "
                f"failing case ids: {list(report.failures)}; nothing pinned"
            ),
        )
    ctx = _build_tool_context(
        req_agent=body.agent,
        db_path=db_path,
        out_dir=out_dir,
        workdir=workdir,
        collections_db=collections_db,
        actor=default_actor,
        x_actor=x_actor,
    )
    # _pin_arguments_jute is idempotent (a caller-supplied sha256 is trusted as-is); pass it through
    # so the pinned params carry BOTH the transform AND its sha256 exactly as the ContractBuilder
    # route does. The 404 (unknown flag) / 422 (malformed) gates fire inside the bound op.
    pinned = ctx.put_grounding_contract(
        flag_code=body.flag_code,
        contract_type="mcp_call",
        params=_pin_arguments_jute(candidate_params),
        question=body.rationale or f"tool-grounded criterion: {body.criterion}"[:280],
        version=f"{body.flag_code}/mcp_call/v1",
        agent=body.agent,
    )
    return {
        "status": "pinned",
        "contract": pinned,
        "gate_report": gate_report,
        "audit_id": f"contract:{body.flag_code}",
    }


@app.post("/v1/grounding-contract")
def put_grounding_contract_endpoint(
    body: GroundingContractRequest,
    db_path: Path = Depends(get_config_db),
    out_dir: Path | None = Depends(get_out_dir),
    workdir: Path = Depends(get_ontology_workdir),
    collections_db: Path = Depends(get_collections_db),
    default_actor: Actor = Depends(get_actor),
    x_actor: str | None = Header(None, alias="X-Actor"),
) -> dict:
    """EVAL-FLOW (W1b): the ContractBuilder card's direct, audited grounding-contract write.

    REUSES the EXACT bound ``ctx.put_grounding_contract`` closure (the SAME one the
    ``add_grounding_contract`` chat tool calls), built via the SAME ``_build_tool_context``
    factory — so there is NO new write logic here: the splice (replace-by-flag-code else
    append) + the FROZEN audited ``put_ontology_endpoint`` are unchanged, and the 404
    (unknown flag) / 422 (malformed) gates hold. The contract lands in the SAME store the
    grade consumes (``ontology.verification_contracts``), so the rail's Ground-truth tick is
    HONEST (W1a reads this store). $0 — no PAID_KEY path.
    """
    ctx = _build_tool_context(
        req_agent=body.agent,
        db_path=db_path,
        out_dir=out_dir,
        workdir=workdir,
        collections_db=collections_db,
        actor=default_actor,
        x_actor=x_actor,
    )
    params = _pin_arguments_jute(body.params or {})
    return ctx.put_grounding_contract(
        flag_code=body.flag_code,
        contract_type=body.contract_type,
        params=params,
        question=body.question,
        version=body.version,
        agent=body.agent,
    )


# ── TOOL-AUTHOR-1: POST/GET/DELETE /v1/tools — author a kind:tool connector per workspace ──────
@app.post("/v1/tools")
def author_tool_endpoint(
    body: AuthoredToolRequest,
    db_path: Path = Depends(get_config_db),
    default_actor: Actor = Depends(get_actor),
    x_actor: str | None = Header(None, alias="X-Actor"),
) -> dict:
    """Declare a ``kind: tool`` connector (an MCP server, an API connector, a KB query, a
    terminology service) into the active workspace's config plane — the SPINE/CONTAINMENT write
    that mirrors POST /v1/judges: validate the manifest, persist per-workspace, audit. The manifest
    carries NO secrets (a connector key rides env via /v1/connector/config). Validation: the
    manifest must be a well-formed ``PluginManifest`` with ``kind == "tool"`` (422 otherwise). The
    optional ``bind`` wires the tool into a judge's flag at grade time (Stage 2). $0, no paid knob."""
    from lithrim_bench.harness import tools_store
    from lithrim_bench.harness.plugins import PluginManifest

    try:
        manifest = PluginManifest.model_validate(body.manifest)
    except Exception as exc:  # noqa: BLE001 — pydantic ValidationError → a clean 422, never a 500
        raise HTTPException(status_code=422, detail=f"invalid tool manifest: {exc}") from exc
    if manifest.kind != "tool":
        raise HTTPException(
            status_code=422, detail=f"manifest kind must be 'tool', got {manifest.kind!r}"
        )
    ws = workspace.get_active_workspace()
    actor = _resolve_actor(x_actor, default_actor)
    tools_store.save_tool(
        manifest.id, body.manifest, bind=body.bind, db_path=db_path, workspace_id=ws.name
    )
    AuditLog(db_path=db_path).record(
        AuditRecord(
            actor=actor,
            action="create",
            target=Target(type="tool", id=manifest.id),
            why={"rationale": body.rationale or f"authored {manifest.implements or 'tool'} {manifest.id}"},
            before=None,
            after={"manifest": body.manifest, "bind": body.bind},
        )
    )
    return {"status": "ok", "tool_id": manifest.id, "actor": actor.model_dump()}


@app.get("/v1/tools")
def list_tools_endpoint(
    db_path: Path = Depends(get_config_db),
) -> dict:
    """The active workspace's tools: ``authored`` (per-workspace, from the config plane) ⊕
    ``declared`` (the core ∪ active-pack ``tool_plugins()`` registry). $0 read, no audit."""
    from lithrim_bench.harness import plugins, tools_store

    ws = workspace.get_active_workspace()
    authored = tools_store.list_tools(db_path=db_path, workspace_id=ws.name)
    declared = [p.model_dump() for p in plugins.tool_plugins(ws.pack)]
    return {"authored": authored, "declared": declared}


@app.delete("/v1/tools/{tool_id}")
def delete_tool_endpoint(
    tool_id: str,
    rationale: str = Query("", description="The author's change reason (the §2B audit 'why')"),
    db_path: Path = Depends(get_config_db),
    default_actor: Actor = Depends(get_actor),
    x_actor: str | None = Header(None, alias="X-Actor"),
) -> dict:
    """Delete an authored tool from this workspace (reversible; the pack-declared tools are
    untouched). Idempotent: a missing tool returns ``removed=false`` with no audit row (the trail
    is change-only). A declared core/pack tool is NOT deletable here (it isn't in authored_tools)."""
    from lithrim_bench.harness import tools_store

    ws = workspace.get_active_workspace()
    actor = _resolve_actor(x_actor, default_actor)
    removed = tools_store.delete_tool(tool_id, db_path=db_path, workspace_id=ws.name)
    if removed:
        AuditLog(db_path=db_path).record(
            AuditRecord(
                actor=actor,
                action="delete",
                target=Target(type="tool", id=tool_id),
                why={"rationale": rationale or f"removed authored tool {tool_id}"},
                before=None,
                after=None,
            )
        )
    return {"status": "ok", "tool_id": tool_id, "removed": removed, "actor": actor.model_dump()}


class ToolTestRequest(BaseModel):
    # TOOL-AUTHOR-1: health-check a kind:tool MCP connector before/after authoring (the card's
    # "Test connection"). `manifest` is the (possibly in-progress) PluginManifest dict.
    manifest: dict


@app.post("/v1/tools/test")
def test_tool_endpoint(body: ToolTestRequest) -> dict:
    """Health-check a stdio-MCP tool: build the McpStdioClient from the manifest's
    ``service.mcp {command, args}`` and ``list_tools()``. Returns ``{ok, tools:[names]}`` or
    ``{ok: false, error}``. LIVE (spawns the MCP server subprocess) but READ-ONLY — never grades,
    never writes. Graceful: a transportless manifest / unreachable server is a calm ``ok=false``,
    never a 500."""
    mcp = ((body.manifest or {}).get("service") or {}).get("mcp") or {}
    cmd = mcp.get("command")
    if not cmd:
        return {"ok": False, "error": "manifest has no service.mcp.command (a stdio MCP) to test"}
    from lithrim_bench.verification.mcp_client import McpStdioClient

    try:
        with McpStdioClient(command=cmd, args=mcp.get("args", [])) as client:
            tools = client.list_tools()
        names = [t.get("name") for t in tools if isinstance(t, dict)]
        return {"ok": True, "tools": names}
    except Exception as exc:  # noqa: BLE001 — bad/unreachable server: report it, never 500
        return {"ok": False, "error": str(exc)}


def _cases_emitting_flag(flag_code: str, examples_dir: Path) -> list[str]:
    """Case ids in ``examples/*.jsonl`` whose ``expected_safety_flags`` include ``flag_code``
    — the corpus-orphan guard for flag delete. A missing dir / unreadable row contributes
    nothing (best-effort: a malformed corpus line must not 500 an honest delete decision; the
    golden lint is the real enforcer)."""
    hits: list[str] = []
    d = Path(examples_dir)
    if not d.exists():
        return hits
    for p in sorted(d.glob("*.jsonl")):
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if flag_code in (row.get("expected_safety_flags") or []):
                hits.append(str(row.get("case_id") or p.name))
    return sorted(set(hits))


@app.delete("/v1/ontology/flags/{flag_code}")
def delete_flag_endpoint(
    flag_code: str,
    agent: str = DEFAULT_AGENT,
    rationale: str = Query("", description="The SME's change reason (the §2B audit 'why')"),
    db_path: Path = Depends(get_config_db),
    workdir: Path = Depends(get_ontology_workdir),
    examples_dir: Path = Depends(get_examples_dir),
    default_actor: Actor = Depends(get_actor),
    x_actor: str | None = Header(None, alias="X-Actor"),
) -> dict:
    """Delete a REFERENCE flag from the agent's ontology working copy (FLAG-1 D3), with an
    actor-attributed immutable audit record (action="delete", target.type="flag", R0).

    REFERENCE-ONLY + orphan-guarded — and CRUCIALLY the three guards live HERE, in the
    endpoint, NOT in any tool wrapper, so they hold for EVERY caller (human, API, agent):
      404  the flag is not in the agent's ontology (nothing to delete);
      422  the flag is gradeable OR in the taxonomy snapshot — a contract code; removing it
           desyncs the contract-of-record, which is a lithrim-backend re-snapshot, never a
           local delete (labels are true by construction);
      422  a persisted judge assigns the flag (a judge orphan — judges are global, S-BS-98);
      422  a committed case emits the flag in expected_safety_flags (a corpus orphan — would
           break the golden lint).
    Only an UNUSED reference flag deletes. NEVER writes the committed seed or the snapshot; the
    write target is the agent-scoped working copy (clobber-safe, mirrors PUT /v1/ontology)."""
    ag = _load_agent(agent, db_path)
    ont_path, _src = _resolve_ontology_path(ag, workdir)
    ontology = json.loads(ont_path.read_text())
    flags = ontology.get("flags") or []
    target_flag = next((f for f in flags if f.get("flag") == flag_code), None)
    if target_flag is None:
        raise HTTPException(status_code=404, detail=f"unknown flag {flag_code!r} (nothing to delete)")
    # GUARD 1 — gradeable / in-snapshot contract code (a re-snapshot, not a local delete).
    if bool(target_flag.get("gradeable")) or flag_code in _active_snapshot_codes():
        raise HTTPException(
            status_code=422,
            detail=(
                f"refusing to delete {flag_code!r}: it is a gradeable / in-snapshot contract code. "
                "Removing a contract code is a lithrim-backend re-snapshot "
                "(scripts/snapshot_taxonomy.py --backend-path …), never a local delete — "
                "labels are true by construction."
            ),
        )
    # GUARD 2 — judge orphan: a persisted (global) judge assigns it; revert that judge first.
    assigned_by = sorted(
        role for role, jc in list_judges(db_path=db_path).items() if flag_code in jc.assigned_flags
    )
    if assigned_by:
        _log.error("refusing to delete %r: judge(s) %s assign it", flag_code, assigned_by)
        reviewers = ", ".join(_reviewer_label(role) for role in assigned_by)
        raise HTTPException(
            status_code=422,
            detail=f"Can't remove this check — it's still used by {reviewers}. Remove it there first.",
        )
    # GUARD 3 — corpus orphan: a committed case emits it (would break the golden lint).
    emitting = _cases_emitting_flag(flag_code, examples_dir)
    if emitting:
        raise HTTPException(
            status_code=422,
            detail=f"refusing to delete {flag_code!r}: case(s) {emitting} emit it in expected_safety_flags",
        )
    # Remove + persist the working copy (mirror put_ontology_endpoint's write), then audit.
    ontology["flags"] = [f for f in flags if f.get("flag") != flag_code]
    _validate_ontology(ontology)  # defensive round-trip: removing a reference flag stays admissible
    workdir.mkdir(parents=True, exist_ok=True)
    path = workdir / f"{agent}.json"
    path.write_text(json.dumps(ontology, indent=2, sort_keys=True))
    actor = _resolve_actor(x_actor, default_actor)
    AuditLog(db_path=db_path).record(
        AuditRecord(
            actor=actor,
            action="delete",
            target=Target(type="flag", id=flag_code),
            why={"rationale": rationale},
            before=target_flag,
            after=None,
        )
    )
    return {"status": "deleted", "flag": flag_code, "agent": agent, "actor": actor.model_dump()}


# ── R0: the two §2B audit streams as why/when/who/what reports ────────────────


@app.get("/v1/audit")
def get_audit_endpoint(
    actor: str | None = Query(None, description="Filter by actor id (the SME handle)"),
    target_type: str | None = Query(None, description="judge | flag | ontology | agent | ..."),
    target_id: str | None = Query(None, description="The acted-upon object id"),
    since: str | None = Query(None, description="Inclusive ISO8601 lower bound on ts"),
    db_path: Path = Depends(get_config_db),
) -> dict:
    """The config-change audit stream (§2B stream 1): who/when/what/why for every
    authoring write, oldest-first, append-only. Filters are ANDed."""
    records = AuditLog(db_path=db_path).query(
        actor=actor, target_type=target_type, target_id=target_id, since=since
    )
    return {"records": records}


@app.post("/v1/meta-verdict")
def post_meta_verdict_endpoint(
    body: MetaVerdictRequest,
    db_path: Path = Depends(get_config_db),
    default_actor: Actor = Depends(get_actor),
    x_actor: str | None = Header(None, alias="X-Actor"),
) -> dict:
    """META-VERDICT-1: record a clinician's INDEPENDENT verdict + judge meta-audit against a
    run — Clinical Scribe Review's Layer-3 (the HITL clinical validator), the surface that was missing.

    A physician reads the council's votes (GET /v1/runs/{id}/audit) and records: their own
    pass/fail, whether they AGREE with the council, and — when they dissent — the judge's
    named fallacy (a closed enum, 422 out-of-enum). It writes exactly ONE immutable
    AuditRecord via the SAME audited-write idiom as ``put_ontology_endpoint``
    (``action=meta_verdict``, ``target=verdict/run_id``) — no engine/``harness/`` file is
    touched. A second submission APPENDS (immutability by construction); the cohort matrix
    (NARR-5-COHORT) joins these records to the run blobs to derive the verdict-match +
    judge-blindness stats. $0 — there is no paid path here.
    """
    actor = _resolve_actor(x_actor, default_actor)
    after = {
        "human_verdict": body.human_verdict,
        "agrees_with_council": body.agrees_with_council,
        "judge_fallacy_code": body.judge_fallacy_code,
    }
    AuditLog(db_path=db_path).record(
        AuditRecord(
            actor=actor,
            action="meta_verdict",
            target=Target(type="verdict", id=body.run_id),
            why={"rationale": body.rationale},
            before=None,
            after=after,
            run_id=body.run_id,
        )
    )
    return {"status": "ok", "run_id": body.run_id, "actor": actor.model_dump(), **after}


def _run_audit_report(doc: dict, run_id: str) -> dict:
    """Project a persisted PipelineProvenance blob into the §2B run-provenance report
    (stream 2): who (the agent) / when (the run ts) / what (the verdict) / why (each
    judge's vote + reasoning + evidence + the final verdict). A faithful, minimal
    projection — the richer query/diff views are UAP-3."""
    semantic = (doc.get("stage_results") or {}).get("semantic") or {}
    judges = [
        {
            "judge_role": v.get("judge_role"),
            "vote": v.get("vote"),
            "confidence": v.get("confidence"),  # float | null
            "model": v.get("model"),
            "reasoning": v.get("reason"),
            "findings": v.get("findings") or [],
            "evidence": semantic.get("evidence") or [],
            "errors": v.get("errors") or [],
        }
        for v in (semantic.get("judge_votes") or [])
    ]
    return {
        "run_id": run_id,
        # RUNTRAIL-6 (SPEC_RUN_AUDIT_TRAIL.md §3 Lineage): a replay is a NEW record that
        # POINTS AT its baseline. Top-level on the blob; None for an authoritative grade.
        "replay_of": doc.get("replay_of"),
        # RUNTRAIL-7 (SPEC §3 Identity): HOW this verdict was produced
        # (replay|in_process|live). Stamped on the blob at persist time (run_eval).
        "grade_path": doc.get("grade_path"),
        "ts": doc.get("timestamp"),
        "actor": {"type": "agent", "id": doc.get("agent_id")},
        "verdict": doc.get("verdict"),
        "gate_decision": doc.get("gate_decision"),
        "verdict_flipped_by_stage": doc.get("verdict_flipped_by_stage"),
        "judges": judges,
        # UAP-3b-2 / S-BS-72: the per-judge withstands ruling (§2B critique stream),
        # embedded into the run-blob by run_eval post-save. Empty on non-gated runs.
        "withstands": doc.get("withstands_decisions") or [],
        "findings": doc.get("findings") or [],
        # LAYER0-READ-1: the post-floor truth, ADDITIVE (the blob `verdict` is pipeline-domain
        # approve/reject; the grounded verdict is composite-domain BLOCK/WARN/PASS — never
        # silently swapped). `grounded` carries active/suppressed(+contract/evidence)/floor_blocks
        # as persisted; None on legacy blobs (pre-fold history projects exactly as before).
        "grounded": doc.get("grounded"),
        "grounded_verdict": (doc.get("grounded") or {}).get("verdict"),
        "stages_executed": doc.get("stages_executed") or [],
        # SIGNATURE-1: config identity + spend truth on the read path. cost_tokens total=0 on an
        # in_process run is the cache-served tell (dspy-live-grade-cache-trap) — now visible.
        "grade_signature": doc.get("grade_signature"),
        "cost_tokens": doc.get("cost_tokens"),
        "grade_config": doc.get("grade_config"),
    }


def _run_summary(doc: dict) -> dict:
    """Newest-first run-history row: the addressable id + the headline verdict +
    who/when, projected from a persisted PipelineProvenance blob (S-BS-56)."""
    grounded = doc.get("grounded")
    return {
        "run_id": doc.get("pipeline_run_id"),
        # RUNTRAIL-11: the case this run graded, so the UI can group the trail per-record.
        "case_id": doc.get("case_id"),
        # RUNTRAIL-6: lineage in the list row too (None for an authoritative grade).
        "replay_of": doc.get("replay_of"),
        # RUNTRAIL-7: the grade path in the list row (replay|in_process|live).
        "grade_path": doc.get("grade_path"),
        "verdict": doc.get("verdict"),
        # LAYER0-READ-1: the post-floor verdict + suppression count in the list row, additive
        # (see _run_audit_report — verdict domains differ, never silently swapped). None on
        # legacy blobs.
        "grounded_verdict": (grounded or {}).get("verdict"),
        "floor_suppressed": len(grounded.get("suppressed") or []) if grounded else None,
        "gate_decision": doc.get("gate_decision"),
        "verdict_flipped_by_stage": doc.get("verdict_flipped_by_stage"),
        "agent": doc.get("agent_id"),
        "ts": doc.get("timestamp"),
        # SIGNATURE-1: same-config comparability + the tokens=0 cache tell, in the list row.
        "grade_signature": doc.get("grade_signature"),
        "cost_tokens": doc.get("cost_tokens"),
    }


@app.get("/v1/runs")
def list_runs_endpoint(
    limit: int = Query(50, ge=1, le=500),
    agent: str | None = None,
    case_id: str | None = None,
    collections_db: Path = Depends(get_collections_db),
) -> dict:
    """The run-history list (R6 read half / S-BS-56): persisted runs newest-first,
    each addressable via its ``run_id`` (round-trips to ``GET /v1/runs/{id}/audit``).
    Replay + in_process + live all persist a provenance blob (S-BS-52), so the $0
    replay default appears here too. Empty list before any run is persisted.

    RUN-TRAIL-CASE-SCOPE: ``agent``/``case_id`` are ADDITIVE filters (the bare call is
    byte-identical). Both given → the store's case-scoped lineage query
    (``list_versions(agent, case_id)`` — Postgres + SQLite twins, newest-first), the same
    query the replay-baseline resolver rides. ``case_id`` is EXACT-match (the
    ``GET /v1/reports/{case_id}`` / ``latest_authoritative_for`` convention — no prefix
    matching exists on this plane). An unknown case is an empty list, never an error.
    Plain (non-Query) defaults on purpose: ``_review_runs`` calls this endpoint directly
    (S-BS-82 — a Query(None) default would arrive as a truthy FieldInfo sentinel)."""
    # PERSIST-2c: read through the factory so run-history reflects the active backend
    # (LITHRIM_DB_URL → Postgres, else the local SQLite at collections_db).
    store = provenance_store_for(collections_db)
    if agent and case_id:
        docs = run_coro(store.list_versions(agent, case_id))[:limit]
    else:
        # single-filter path: filter over the full newest-first read, THEN truncate —
        # a windowed read would silently drop older matching runs.
        docs = run_coro(store.list_all(limit=None if (agent or case_id) else limit))
        if agent:
            docs = [d for d in docs if d.get("agent_id") == agent]
        if case_id:
            docs = [d for d in docs if d.get("case_id") == case_id]
        docs = docs[:limit]
    return {"runs": [_run_summary(d) for d in docs]}


@app.get("/v1/runs/{run_id}/audit")
def get_run_audit_endpoint(
    run_id: str,
    collections_db: Path = Depends(get_collections_db),
) -> dict:
    """The run-provenance audit report (§2B stream 2) for a persisted run. Reads the
    SqliteProvenanceStore blob SYNCHRONOUSLY via the doc-shim's sync .get (no event
    loop in the sync handler) and projects the per-judge votes/reasoning/evidence +
    final verdict.

    UAP-3 (S-BS-52): replay + live + in_process all persist a provenance blob now, so
    any run that actually ran is auditable. An unknown / never-run id is still a clean
    404 — never a 500 (monitor N1)."""
    # PERSIST-2c: read through the factory (LITHRIM_DB_URL → Postgres, else local SQLite).
    doc = run_coro(provenance_store_for(collections_db).find_by_id(run_id))
    if doc is None:
        raise HTTPException(
            status_code=404,
            detail=f"run {run_id!r} not found (no persisted provenance blob for this run id)",
        )
    return _run_audit_report(doc, run_id)


@app.get("/v1/runs/{run_id}/history")
def get_run_history_endpoint(
    run_id: str,
    collections_db: Path = Depends(get_collections_db),
) -> dict:
    """RUNTRAIL-6 / SPEC §2: the archived prior versions of a run, newest-first — the
    read-surface for the versioned copy-on-write archive (``list_history``, RUNTRAIL-2/G4).
    A same-id re-save copies the prior doc into the ``_history`` shadow; this surfaces that
    lineage so the trail's prior states are auditable, not just the head.

    404 only when the run id itself is unknown (no head blob). A KNOWN-but-unsuperseded run
    returns ``{"history": []}`` — an empty archive is a valid state, not a missing run."""
    # PERSIST-2c: read through the factory (LITHRIM_DB_URL → Postgres, else local SQLite).
    store = provenance_store_for(collections_db)
    if run_coro(store.find_by_id(run_id)) is None:
        raise HTTPException(
            status_code=404,
            detail=f"run {run_id!r} not found (no persisted provenance blob for this run id)",
        )
    history = run_coro(store.list_history(run_id))
    return {"run_id": run_id, "history": [_run_summary(d) for d in history]}


@app.get("/v1/runs/{run_id}/rehydrate")
def get_run_rehydrate_endpoint(
    run_id: str,
    collections_db: Path = Depends(get_collections_db),
) -> dict:
    """RUNTRAIL-6 / SPEC §4: reconstruct the graded result from the stored run blob ALONE —
    no live model call, no re-grade ($0 by construction). Proves the record is self-sufficient.

    Composes ``provenance.rehydrate`` (``find_by_id`` → ``provenance_to_result``, the pure
    blob→result adapter above the frozen seam), resolved through the SAME store precedence the
    grade path uses (``LITHRIM_DB_URL`` → Postgres, else the local SQLite ``collections_db``).
    Unknown id → ``LookupError`` → clean 404 (never a 500)."""
    from lithrim_bench.runtime.pipeline.provenance import rehydrate

    try:
        return rehydrate(run_id, db_path=collections_db)
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"run {run_id!r} not found (no persisted provenance blob for this run id)",
        ) from exc


@app.get("/v1/reports/{case_id}")
def get_case_report_endpoint(
    case_id: str,
    agent: str = DEFAULT_AGENT,
    out_dir: Path | None = Depends(get_out_dir),
) -> dict:
    """REPORT-HYDRATE-1 — the LATEST persisted report record for ``case_id``, as a pure $0
    READ (no re-grade, no replay, no run-row append): the SAME record shape POST /v1/run-eval
    returns, so the shell's Report tab hydrates an armed case's last saved result with the
    EXACT renderer the in-session run feeds (no parallel projection). Reads the ``persist()``
    store (the per-case upserted record every grade path writes) and applies the SAME
    read-side folds run-eval applies (calibration_check / grade_path / council /
    pipeline_run_id).

    HONESTY: 404 when nothing is persisted for the case, and 404 when the stored record
    belongs to a DIFFERENT agent (never serve another agent's verdict under this agent's
    name). It never trips the SIGNATURE-1 freshness guard — this serves what IS stored,
    honestly labeled by its stored ``grade_path``; staleness policy stays on the replay/grade
    paths (a hydrated view is a record of the last grade, not a claim of freshness)."""
    from lithrim_bench.harness.persist import DEFAULT_OUT_DIR
    from lithrim_bench.harness.persist import load as load_report

    root = Path(out_dir) if out_dir else DEFAULT_OUT_DIR
    record = load_report(case_id, db_path=root / "ws0.sqlite")
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"no persisted report for case {case_id!r} (run an evaluation first)",
        )
    stored_agent = record.get("agent")
    if agent and stored_agent is None:
        # Critic tighten: an agent-LESS (legacy) record is unattributable — serving it under
        # whatever agent asks is the same silent mis-attribution the mismatch guard stops.
        raise HTTPException(
            status_code=404,
            detail=(
                f"the persisted report for case {case_id!r} is a legacy record with no agent "
                f"stamp — re-grade the case to claim it for {agent!r}"
            ),
        )
    if agent and stored_agent != agent:
        raise HTTPException(
            status_code=404,
            detail=(
                f"the persisted report for case {case_id!r} belongs to agent "
                f"{stored_agent!r}, not {agent!r} (run an evaluation for this agent first)"
            ),
        )
    record.pop("_persisted", None)
    record["calibration_check"] = calibration_check([record])
    record["grade_path"] = (record.get("provenance") or {}).get("grade_path")
    record["council"] = _council_view(record)
    record["pipeline_run_id"] = _pipeline_run_id(record)
    return record


# ── REL-OPS-1 / O3: the longitudinal meta-eval READ surface ─────────────────────────
# "The evaluator's own accuracy, dated" (SPEC_RELIABILITY_PROGRAM O3): a pure-read join
# over ingredients that already exist — the immutable run-history blobs (RUNTRAIL SoT),
# the per-case gold (_corpus_golds_labeled, the SAME derivation the RUN-ALL-1 cohort
# scorecard reads), and the META-VERDICT-1 clinician AuditRecords. No new write path,
# no engine edit, no consensus touch. Honesty: an absent join is an explicit null.


def _meta_eval_timeline_row(
    doc: dict, golds: dict[str, set], labeled: set, metas: dict[str, list[dict]]
) -> dict:
    """One dated timeline row from a persisted run blob: identity (run_id/ts/case/
    grade_signature/grade_path), the model roster AS RECORDED (the semantic-stage
    judge_votes), verdict-vs-gold agreement where the case carries gold, and the
    clinician meta-verdict where a META-VERDICT-1 record exists — both ``null`` when
    the join is absent (never a fabricated value)."""
    semantic = (doc.get("stage_results") or {}).get("semantic") or {}
    raised = sorted(
        {
            f.get("code")
            for f in (doc.get("findings") or [])
            if isinstance(f, dict) and f.get("code")
        }
    )
    row = {
        "run_id": doc.get("pipeline_run_id"),
        "ts": doc.get("timestamp"),
        "case_id": doc.get("case_id"),
        "verdict": doc.get("verdict"),
        "gate_decision": doc.get("gate_decision"),
        # null on blobs persisted before grade_path stamping — honest absence
        "grade_path": doc.get("grade_path"),
        "grade_signature": doc.get("grade_signature"),
        "models": [
            {"judge_role": v.get("judge_role"), "model": v.get("model")}
            for v in (semantic.get("judge_votes") or [])
        ],
        "raised": raised,
        "gold": None,
        "meta_verdict": None,
    }
    cid = doc.get("case_id")
    if cid in labeled:
        gold = golds.get(cid, set())
        raised_set = set(raised)
        row["gold"] = {
            "expected": sorted(gold),
            "caught": sorted(gold & raised_set),
            "missed": sorted(gold - raised_set),
            "spurious": sorted(raised_set - gold),
            # the RUN-ALL-1 scorecard rule: gold present <=> a blocked verdict
            "verdict_match": bool(gold) == _is_blocked_verdict(doc.get("verdict")),
        }
    recs = metas.get(row["run_id"]) or []
    if recs:
        latest = recs[-1]  # AuditLog.query returns oldest-first; the newest record wins
        after = latest.get("after") or {}
        row["meta_verdict"] = {
            "n_records": len(recs),
            "ts": latest.get("ts"),
            "actor": (latest.get("actor") or {}).get("id"),
            "human_verdict": after.get("human_verdict"),
            "agrees_with_council": after.get("agrees_with_council"),
            "judge_fallacy_code": after.get("judge_fallacy_code"),
        }
    return row


def _signature_segments(rows: list[dict]) -> list[dict]:
    """Contiguous same-``grade_signature`` stretches over the oldest-first timeline —
    a signature change is a SERIES BREAK (the config drifted; agreement numbers on
    either side are not comparable). Purely derived from the per-row signatures."""
    segments: list[dict] = []
    for row in rows:
        sig = row.get("grade_signature")
        if not segments or segments[-1]["grade_signature"] != sig:
            segments.append(
                {"grade_signature": sig, "start_ts": row.get("ts"),
                 "end_ts": row.get("ts"), "n_runs": 0}
            )
        segments[-1]["end_ts"] = row.get("ts")
        segments[-1]["n_runs"] += 1
    return segments


@app.get("/v1/meta-eval/timeline")
def meta_eval_timeline_endpoint(
    agent: str = Query(DEFAULT_AGENT),
    limit: int = Query(500, ge=1, le=2000),
    db_path: Path = Depends(get_config_db),
    collections_db: Path = Depends(get_collections_db),
) -> dict:
    """O3 — the agent-scoped, dated series of runs joined to their agreement outcomes,
    OLDEST-first (a time series, not the newest-first run list). Per run: identity +
    ``grade_signature`` + recorded models + gold agreement + clinician meta-verdict;
    plus ``signature_segments`` so a config change reads as a series break. Unknown
    agent → 404 (the ``_load_agent`` convention); a known agent with no runs → an
    empty timeline. Pure read, $0."""
    _load_agent(agent, db_path)
    docs = run_coro(provenance_store_for(collections_db).list_all(limit=None))
    mine = [d for d in docs if d.get("agent_id") == agent]
    mine.sort(key=lambda d: str(d.get("timestamp") or ""))
    mine = mine[-limit:]
    golds, labeled = _corpus_golds_labeled(_read_ingested_corpus())
    metas: dict[str, list[dict]] = {}
    for rec in AuditLog(db_path=db_path).query(target_type="verdict"):
        if rec.get("action") != "meta_verdict":
            continue
        rid = (rec.get("target") or {}).get("id")
        if rid:
            metas.setdefault(rid, []).append(rec)
    rows = [_meta_eval_timeline_row(d, golds, labeled, metas) for d in mine]
    return {
        "agent": agent,
        "n_runs": len(rows),
        "timeline": rows,
        "signature_segments": _signature_segments(rows),
    }


@app.get("/v1/kb/{namespace}/search")
def kb_search_endpoint(
    namespace: str,
    q: str = Query(..., min_length=1, description="The claim text to ground against the KB"),
    top_k: int = Query(5, ge=1, le=20),
    min_score: float = Query(0.0),
    match: str | None = Query(None, description="Corroboration predicate (e.g. 'claim_in_chunk')"),
    service: str = Depends(get_kb_service),
    http_client: Any | None = Depends(get_kb_http_client),
) -> dict:
    """KB-grounding check (WS-7b, the first Phase-3 slice) — compose over the harness
    ``KbRagTool``, which fronts the backend KB at ``GET :8002/v1/kb/{namespace}/search``.

    Additive + thin: it builds a ``Claim`` from ``q`` and returns the tool's tri-state
    grounding verdict (``conforms``: True=KB grounds the claim, None=inconclusive) plus
    the retrieved matches and the determinism manifest. The heavy retrieval stays in
    lithrim-backend (no vector store here). ``http_client`` is injectable so tests mock
    :8002; in production it is ``None`` and the tool creates an ``httpx.Client`` lazily
    (the ``[bff]`` extra carries httpx). A KB / transport error degrades to
    ``conforms=None`` with the error surfaced in ``manifest`` — never a fabricated hit.
    """
    from lithrim_bench.verification import (
        REFERENCE_CONFORMANCE,
        Claim,
        KbRagTool,
        VerificationSpec,
    )

    reference: dict[str, Any] = {"namespace": namespace, "service": service, "top_k": top_k}
    if min_score:
        reference["min_score"] = min_score
    if match:
        reference["match"] = match
    try:
        spec = VerificationSpec(
            tool="kb_rag",
            applies_to_flags=(),
            locus="",
            reference=reference,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"bad kb spec: {exc}") from exc

    claim = Claim(claim_type=REFERENCE_CONFORMANCE, flag_code=None, subject=q)
    result = KbRagTool(http_client=http_client).verify(claim, spec)
    return {
        "namespace": namespace,
        "query": q,
        "conforms": result.conforms,
        "disposition": result.disposition,
        "evidence": result.evidence,
        "manifest": result.manifest,
    }


def _resolve_chat_agent(req_agent: str, db_path: Path) -> str:
    """CONV-UX-1 (W0): resolve the chat turn's effective agent against the ACTIVE
    workspace's config DB. The live 404 cascade was twofold: the model emits the literal
    ``ws0_default`` as an explicit tool arg AND the shell defaults ``activeAgent`` to
    ``ws0_default``, but a non-``default`` workspace (e.g. ``demo-clinical``, agents
    ``eval-1``/``snomed-demo``) has no such agent — so every agent-keyed tool (get_agent,
    show_case, run_eval, the ontology read) 404s.

    GUARDRAIL: a VALID supplied agent (present in this DB) is HONORED verbatim — multi-
    agent targeting must keep working. Only an INVALID/absent supplied agent is COERCED to
    the workspace's first agent. Back-compat: in ``default`` (which holds ``ws0_default``)
    the literal still resolves to itself. Last resort (no agents at all) falls back to the
    DEFAULT_AGENT literal so the loop can still surface the 404 honestly rather than crash.

    Mirrors ``_load_agent``'s seed-on-first-use so a fresh workspace DB resolves the seeded
    agent before any authoring."""
    try:
        if not db_path.exists():
            seed_config_db(db_path=db_path)
        names = list_agents(db_path=db_path)
    except Exception:  # noqa: BLE001 — a DB read failure must not break the chat; keep the ask
        return req_agent
    if req_agent in names:
        return req_agent  # GUARDRAIL: honor a valid (incl. explicitly-targeted) agent
    if names:
        return names[0]  # coerce an invalid/stale arg to the active workspace's first agent
    return req_agent  # no agents on disk — keep the ask so the loop surfaces the honest 404


def _build_tool_context(
    req_agent: str,
    db_path: Path,
    out_dir: Path | None,
    workdir: Path,
    collections_db: Path,
    actor: Actor,
    x_actor: str | None,
    active_case: str | None = None,
):
    """Bind the EXISTING endpoint functions (deps resolved) into a ToolContext for the
    agent loop (UAP-5b D3). The closures call the FROZEN ops directly — every gate
    (owner↔emit / snapshot) + the audited write path stay intact. apps/bff/agent never
    imports app.py; app.py injects the ops here → no circular import.

    A-SAFE: ``run_eval_replay`` hardcodes ``live=in_process=False`` — there is NO
    branch, here or in the tool, that yields a paid run. The agent proposes a paid run
    in prose; only the human's in-DOM cost-confirm hits the existing confirm-gated path.
    """
    from agent import ToolContext  # lazy: keep [agent] off app import (no SDK pulled here)

    def _author_judge(
        role: str, assigned_flags: list[str], rationale: str, model: str = ""
    ) -> dict:
        # BYOC-1 (resolves NB-2): ``model`` is the provider selector — "" binds the
        # default Azure LM, "byo-claude" binds the tool-less BYO-Claude judge. Persisted
        # via the unchanged ``put_judge_endpoint`` (audited; not a paid run).
        body = {"assigned_flags": assigned_flags, "validator_refs": [], "model": model or ""}
        return put_judge_endpoint(
            role,
            judge=body,
            rationale=rationale,
            db_path=db_path,
            default_actor=actor,
            x_actor=x_actor,
        )

    def _delete_judge(role: str, rationale: str = "") -> dict:
        # CRUD-1 (D3): REVERT a judge to its default lens via the FROZEN audited delete op
        # (remove its JudgeConfig). Reversible + bounded — the bound op is revert-only, so the
        # agent can NEITHER delete an agent NOR fire a paid run. Per the S-BS-82 rule, pass
        # every Query/Header param explicitly (a direct call bypasses the FastAPI router).
        return delete_judge_endpoint(
            role,
            rationale=rationale,
            db_path=db_path,
            default_actor=actor,
            x_actor=x_actor,
        )

    def _get_judge(role: str) -> dict:
        # S-BS-82: pass assigned_flags=None EXPLICITLY. Calling an endpoint as a plain
        # function bypasses the FastAPI router, so an omitted Query(...)/Header(...)
        # param keeps its FieldInfo sentinel — Query(None) is `not None`, so the live
        # `assigned_flags.split(",")` crashed. Binding rule (applies to EVERY closure
        # here): pass all Query/Header params explicitly when calling an op directly.
        return get_judge_endpoint(
            role, agent=req_agent, assigned_flags=None, db_path=db_path, workdir=workdir
        )

    def _run_eval_replay(agent: str, case_id: str | None = None) -> dict:
        # NARR-CHAT-LOOP: ``case_id`` selects the ingested case to grade (the chat's "run case X" /
        # the shared active case); ``None`` keeps the agent's own dataset.case_id. A-SAFE is
        # untouched — live=in_process=False is hardcoded, so the case selector never becomes a spend.
        return run_eval_endpoint(
            RunEvalRequest(agent=agent, case_id=case_id, live=False, in_process=False),
            db_path=db_path,
            out_dir=out_dir,
            workdir=workdir,
            collections_db=collections_db,
        )

    def _list_cases() -> dict:
        # NARR-CHAT-LOOP: the chat's list_cases reaches the SAME ingested corpus GET /v1/cases
        # serves (the UI Cases tab). list_cases_endpoint takes no deps — it reads the active
        # workspace's ingested_cases.jsonl. $0/read.
        return list_cases_endpoint()

    def _known_case_ids() -> list[str]:
        # CHAT-CASE-TOKEN-RESOLVE: the agent's resolvable case ids (the GET /v1/cases/browser
        # source) so the tool layer can map a short/prefix token to the unique full id. $0/read.
        return _agent_known_case_ids(req_agent, db_path)

    def _load_case_full(case_id: str) -> dict | None:
        # GROUNDED-EXPLAIN-1: resolve a case's raw dict (transcript/context + artifacts + gold)
        # the SAME way GET /v1/case does — pin the active agent's source so the workspace-corpus
        # resolution works in this request context (the source-less load_case can't reach it from
        # the agent loop). $0/read; never a spend.
        if not case_id:
            return None
        ag = _load_agent(req_agent, db_path)
        return load_case(case_id, source=ag.source_abspath())

    # ── UAP-5c: the journey-completing closures (Domain / Flag / Review). Each wraps a
    # FROZEN op and (per the S-BS-82 rule) passes every Query/Header param explicitly.
    def _get_agent(name: str) -> dict:
        return get_agent_endpoint(name=name, db_path=db_path)

    def _author_flag(
        flag_code: str,
        tier=None,
        gradeable=None,
        rationale: str = "",
        definition: str | None = None,
        when_to_use: str | None = None,
        when_NOT_to_use: str | None = None,
    ) -> dict:
        # Edit an EXISTING flag's tier/gradeable/criterion-text in the current ontology, then
        # PUT the merged ontology through the FROZEN audited op (clobber-safe working copy).
        # CRITERION-TEXT-1: when_to_use is the lens line judge_assignment renders into the
        # judge's prompt — rewording it here IS the calibration edit (SIGNATURE-1 then stales
        # prior heads honestly). None = untouched; an explicit "" clears. We never fabricate
        # owner_roles or invent a flag — that stays the human's act.
        ag = _load_agent(req_agent, db_path)
        ont_path, _src = _resolve_ontology_path(ag, workdir)
        ontology = json.loads(ont_path.read_text())
        match = next((f for f in (ontology.get("flags") or []) if f.get("flag") == flag_code), None)
        if match is None:
            raise HTTPException(status_code=404, detail=f"unknown flag {flag_code!r} (edit an existing flag)")
        if tier is not None:
            match["tier"] = tier
        if gradeable is not None:
            match["gradeable"] = bool(gradeable)
        if definition is not None:
            match["definition"] = str(definition)
        if when_to_use is not None:
            match["when_to_use"] = str(when_to_use)
        if when_NOT_to_use is not None:
            match["when_NOT_to_use"] = str(when_NOT_to_use)
        put = put_ontology_endpoint(
            ontology=ontology,
            agent=req_agent,
            rationale=rationale,
            db_path=db_path,
            workdir=workdir,
            default_actor=actor,
            x_actor=x_actor,
        )
        return {
            "flag": flag_code, "tier": match["tier"], "gradeable": match["gradeable"],
            "when_to_use": match.get("when_to_use", ""), **put,
        }

    def _create_flag(
        flag_code: str,
        category: str,
        definition: str,
        when_to_use: str = "",
        when_NOT_to_use: str = "",
        rationale: str = "",
    ) -> dict:
        # FLAG-1 (D1): CREATE a NEW *reference* flag. gradeable/tier/owner_roles are HARDCODED
        # here (gradeable=False, tier=None, owner_roles=[]) — NEVER read from args, and the tool
        # schema carries no gradeable knob — so the create path can NEVER produce a gradeable /
        # scoreable flag. A gradeable flag requires a lithrim-backend re-snapshot (labels are true
        # by construction; CLAUDE.md). 409 if the code already exists (create != edit — editing an
        # existing flag stays author_flag). Persisted via the FROZEN audited put_ontology_endpoint
        # (so _validate_ontology runs and the action="edit" audit on target=ontology fires — the
        # before->after diff IS the create evidence).
        ag = _load_agent(req_agent, db_path)
        ont_path, _src = _resolve_ontology_path(ag, workdir)
        ontology = json.loads(ont_path.read_text())
        flags = ontology.get("flags") or []
        if any(f.get("flag") == flag_code for f in flags):
            raise HTTPException(
                status_code=409,
                detail=f"flag {flag_code!r} already exists (edit it via author_flag; create adds a new one)",
            )
        flags.append(
            {
                "flag": flag_code,
                "category": category,
                "definition": definition,
                "when_to_use": when_to_use,
                "when_NOT_to_use": when_NOT_to_use,
                "owner_roles": [],  # HARDCODED — reference flags are unowned; never invent owners (D-D)
                "tier": None,  # HARDCODED — out-of-snapshot, untiered
                "gradeable": False,  # HARDCODED — the create can NEVER make a gradeable flag (the one law)
                "reliability_pillar": None,
            }
        )
        ontology["flags"] = flags
        put = put_ontology_endpoint(
            ontology=ontology,
            agent=req_agent,
            rationale=rationale,
            db_path=db_path,
            workdir=workdir,
            default_actor=actor,
            x_actor=x_actor,
        )
        return {"flag": flag_code, "gradeable": False, "tier": None, "owner_roles": [], **put}

    def _delete_flag(flag_code: str, rationale: str = "") -> dict:
        # FLAG-1 (D3): the agent-reachable flag DELETE. This wrapper ONLY binds-and-forwards
        # params explicitly (S-BS-82 — a direct call bypasses the FastAPI router, so omitted
        # Query/Depends params would stay FieldInfo sentinels). ALL guards (gradeable/in-snapshot,
        # judge-assigned, case-emitted) live in delete_flag_endpoint, NOT here, so they hold for
        # EVERY caller — the agent can delete only an UNUSED reference flag, never a contract code.
        return delete_flag_endpoint(
            flag_code,
            agent=req_agent,
            rationale=rationale,
            db_path=db_path,
            workdir=workdir,
            examples_dir=get_examples_dir(),
            default_actor=actor,
            x_actor=x_actor,
        )

    def _review_runs(limit: int = 5, case_id: str | None = None) -> dict:
        # CHATBIND-1 (S-BS-103): SCOPE the run history to the ACTIVE agent (req_agent) so
        # "review the runs" shows the rail-selected case's runs, not the global history. The
        # frozen list_runs_endpoint is unscoped, so fetch a generous newest-first window (200,
        # < the endpoint's 500 cap), filter on the `agent` field every row already carries
        # (_run_summary -> agent_id; replay/in_process/live all backfill it), then truncate to
        # `limit`. latest_id/latest_audit then reflect the ACTIVE agent's latest run.
        # RUN-TRAIL-CASE-SCOPE: case_id given → the case the human NAMED is the scope —
        # the endpoint's (agent, case_id) lineage read; latest_id = the latest run OF THAT
        # CASE, not the agent's newest run on any case (the 2026-07-04 live defect). The
        # scope echoes back (`case_id`) so the tool narrates what it scoped to.
        if case_id:
            listing = list_runs_endpoint(
                limit=int(limit) if limit else 5, agent=req_agent, case_id=case_id,
                collections_db=collections_db,
            )
            runs = listing.get("runs") or []
        else:
            listing = list_runs_endpoint(
                limit=200, agent=None, case_id=None, collections_db=collections_db
            )
            runs = [r for r in (listing.get("runs") or []) if r.get("agent") == req_agent][:limit]
        latest_id = runs[0].get("run_id") if runs else None
        latest_audit = None
        if latest_id:
            try:
                latest_audit = get_run_audit_endpoint(latest_id, collections_db=collections_db)
            except HTTPException:
                latest_audit = None
        return {
            "runs": runs, "latest_run_id": latest_id, "latest_audit": latest_audit,
            "case_id": case_id,
        }

    # ── UAP-5c-2: the eval-pack BATCH closure (the first wrapper over a PAID-CAPABLE op).
    def _run_eval_pack(pack_id: str, agents: list[str]) -> dict:
        # A-SAFE crux: eval_pack_run_endpoint's `live` knob fires one paid :8002 call per
        # agent. The wrapper HARDCODES live=False — there is NO branch, here or in the tool,
        # that yields a paid batch (mirrors _run_eval_replay). Per the S-BS-82 rule, pass
        # every Depends param explicitly (a direct call bypasses the FastAPI router).
        return eval_pack_run_endpoint(
            EvalPackRunRequest(pack_id=pack_id, agents=agents, live=False),
            db_path=db_path,
            out_dir=out_dir,
            collections_db=collections_db,
            workdir=workdir,
        )

    # ── UAP-5c-2: the Domain-assembly WRITE closure (EDIT-ONE-FACET: the judges roster).
    def _assemble_agent(
        name: str, add_judge=None, remove_judge=None, rationale: str = ""
    ) -> dict:
        # EDIT-ONE-FACET (the judges roster): load the current Agent dict via the FROZEN GET
        # op, add/remove ONE KNOWN v2 judge (LENS_BY_ROLE is the role authority — refuse an
        # unknown role, never fabricate a judge), then PUT the merged dict through the FROZEN
        # audited op (422 on malformed). We never trust a full agent dict from the model. Per
        # the S-BS-82 rule, pass every Query/Header param to put_agent_endpoint explicitly.
        current = get_agent_endpoint(name=name, db_path=db_path)  # 404 on unknown agent
        judges = list(current["eval_profile"].get("judges") or [])
        if not add_judge and not remove_judge:
            raise HTTPException(status_code=400, detail="specify add_judge or remove_judge")
        if add_judge:
            if add_judge not in LENS_BY_ROLE:
                raise HTTPException(
                    status_code=404,
                    detail=f"unknown judge role {add_judge!r} (known: {sorted(LENS_BY_ROLE)})",
                )
            if add_judge not in judges:
                judges.append(add_judge)
        if remove_judge and remove_judge in judges:
            judges.remove(remove_judge)
        current["eval_profile"]["judges"] = judges
        put = put_agent_endpoint(
            agent=current,
            rationale=rationale,
            db_path=db_path,
            default_actor=actor,
            x_actor=x_actor,
        )
        return {"name": name, "judges": judges, **put}

    # ── GROUND-CHAT-1: the conversational "add grounding contracts" WRITE (step 5 by voice).
    def _put_grounding_contract(
        flag_code: str, contract_type: str, params: dict | None = None,
        question: str = "", version: str = "", agent: str = "",
    ) -> dict:
        # Mirrors _create_flag: read the DRAFT ontology directly (NO GET endpoint, so no FastAPI
        # FieldInfo sentinels — the S-BS-82 trap), splice/replace the verification_contracts entry
        # by flag_code, then PUT via the FROZEN audited put_ontology_endpoint (so _validate_ontology
        # runs + the action="edit"/target=ontology audit fires). Per S-BS-82, every Query/Header/
        # Depends param is passed explicitly. $0 config write; guards (snapshot/validate) hold for all.
        ag_name = agent or req_agent
        ag = _load_agent(ag_name, db_path)
        ont_path, _src = _resolve_ontology_path(ag, workdir)
        ontology = json.loads(ont_path.read_text())
        if not any(f.get("flag") == flag_code for f in (ontology.get("flags") or [])):
            raise HTTPException(
                status_code=404, detail=f"unknown flag {flag_code!r} (create the flag first)"
            )
        # FAUTH-2 (G3 / OQ-2 — the spine invariant's enforceable second half, at AUTHOR time):
        # refuse a contract_type with no registered DETERMINISTIC executor in the active WORKSPACE's
        # grade pack, BEFORE the splice/PUT. This moves the grade-time RAISE (grounding.py:599-600 —
        # "no executor registered", a 500 mid-batch) up to a clean 422 here, so a prose / free-text /
        # future-"openevidence_judge" type can never be pinned. READ-ONLY against the moat: it
        # CALLS the public accessors (suppress ∪ floor) — it never edits grounding.py/ground()/the
        # executors. The 404 (unknown flag) above still takes precedence; nothing is persisted on
        # reject (the raise precedes put_ontology_endpoint). The deeper oracle_kind executor-marker
        # gate (refuse a free-text executor at the accessor itself) is FAUTH-2b (cross-repo: the
        # external pack executors carry no marker yet → a fail-closed marker-gate would drop the
        # clinical floors). The chat handler's broad except surfaces this 422 as honest guidance.
        # FAUTH-2a (S-BS-FAUTH2-2, the S-BS-154 family): resolve the active WORKSPACE's grade pack
        # (NOT the BFF process pack, live = _core) so the gate admits exactly what the grade
        # subprocess will run — else it false-rejects the clinical floors on a healthcare workspace.
        from lithrim_bench.harness import grounding as _grounding
        from lithrim_bench.harness import workspace as _workspace

        _ws_pack = _workspace.get_active_workspace().pack
        registered = set(_grounding.suppress_executors(_ws_pack)) | set(_grounding.floor_executors(_ws_pack))
        if contract_type not in registered:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"contract_type {contract_type!r} has no registered executor for the active "
                    f"pack — it would raise at grade time. Use one of: {sorted(registered)}."
                ),
            )
        # GRADE-GUARD-1: validate the PARAMS shape (not only the type) by dry-constructing the
        # contract — a presence_check authored with the inert default (no med_source) is rejected
        # HERE (422) instead of detonating ground() with a cryptic KeyError mid-grade (the live
        # A-LIVE crash). READ-ONLY: validate_contract_params constructs + discards; never grades.
        from lithrim_bench.harness.ontology import VerificationContractDecl

        try:
            _grounding.validate_contract_params(
                VerificationContractDecl(
                    flag_code=flag_code,
                    question=question,
                    contract_type=contract_type,
                    params=params or {},
                    version=version,
                ),
                pack=_ws_pack,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        entry = {
            "contract_type": contract_type,
            "flag_code": flag_code,
            "question": question,
            "params": params or {},
            "version": version,
        }
        contracts = ontology.get("verification_contracts") or []
        idx = next((i for i, c in enumerate(contracts) if c.get("flag_code") == flag_code), None)
        replaced = idx is not None
        if replaced:
            contracts[idx] = entry
        else:
            contracts.append(entry)
        ontology["verification_contracts"] = contracts
        put = put_ontology_endpoint(
            ontology=ontology,
            agent=ag_name,
            rationale=f"grounding contract ({contract_type}) for {flag_code}",
            db_path=db_path,
            workdir=workdir,
            default_actor=actor,
            x_actor=x_actor,
        )
        return {"flag_code": flag_code, "version": version, "replaced": replaced, **put}

    # ── NARR-2: the "eval anything" INGESTION binding — drop JSON → generate a JUTE transform →
    # live-gate on :3031 → apply → PIN → upsert the workspace corpus + write ONE AuditRecord.
    def _ingest_cases(
        json_dump: str,
        extraction_rules: str = "",
        agent: str = "",
        expected_count: int | None = None,
        *,
        approved_template: str | None = None,
        pin_template: bool = True,
        commit_corpus: bool = True,
    ) -> dict:
        # CE-INGEST-FRONTDOOR-1 (the preview/commit split, all defaults = the unchanged chat path):
        #   approved_template — skip the 3-way selection + LM gen; re-gate THIS exact human-approved
        #                       template on the data (the COMMIT path).
        #   pin_template      — False on PREVIEW: select/generate a template but pin NOTHING.
        #   commit_corpus     — False on PREVIEW: do NOT upsert the corpus / write an audit row;
        #                       return the extracted cases + template for the human to validate.
        # INGESTION-ONLY (trust-model separation, SPEC_NARRATIVE_EVAL A4): this builds + pins a
        # jute_transform via EtlpJuteClient DIRECTLY (like add_grounding_contract calls its bound
        # write) — the extractor NEVER enters _CONTRACT_EXECUTORS / the grade-time floor. $0/BYO-key
        # author transform, never a paid council run. The structural output-invariant
        # (score_extraction) gates BOTH at generation time (live test_template) and at apply time;
        # a mis-join returns null → rejected (RuntimeError surfaced by the handler), NOTHING pinned.
        from lithrim_bench.harness import workspace as _ws
        from lithrim_bench.verification import (
            EtlpJuteClient,
            best_of_n_extractor,
            build_extractor_generator,
            render_dsl_excerpt,
            required_case_fields,
            score_extraction,
        )

        ag_name = agent or req_agent
        try:
            sample = json.loads(json_dump)
        except json.JSONDecodeError as exc:
            # REPRO-1 R1a: the chat path receives a raw STRING — a JSONL corpus (one case per
            # line) must parse like the front door does (parse-in-Python is the house rule).
            # Only the jsonl sniff is accepted here; anything else keeps the honest JSON error.
            from lithrim_bench.verification.ingest_decode import decode_records

            try:
                dec = decode_records(json_dump, fmt="auto")
            except Exception:
                dec = None
            if dec is None or dec.fmt != "jsonl":
                raise RuntimeError(f"the ingested JSON did not parse: {exc}") from exc
            sample = dec.sample
            if expected_count is None:
                expected_count = dec.expected_count

        # ── the shared tail: label-merge + source-normalize + preview/commit + ONE audit row.
        def _finalize(
            cases: list[dict],
            *,
            template: str | None = None,
            mapping_id=None,
            reused: bool = False,
            hand_authored: bool = False,
            native: bool = False,
        ) -> dict:
            labeled = _merge_byo_labels(cases, sample)
            # REPRO-1 R1a: preserve the source's structured record (`patient_profile`) onto the
            # produced cases — the non-native envelope drops it, and the record is what R1b renders
            # for the record-vs-note floor. Optional + non-clobbering (the native verbatim record
            # stays), mirroring the label merge above.
            _merge_source_record(cases, sample)
            normalized = _normalize_case_source(cases)
            if not commit_corpus:
                return {
                    "cases": cases, "template": template, "mapping_id": mapping_id,
                    "count": len(cases), "labeled": labeled, "normalized_source": normalized,
                    "reused": reused, "hand_authored": hand_authored, "native": native,
                    "preview": True,
                }
            ws = _ws.get_active_workspace()
            corpus_path = ws.out_dir / "ingested_cases.jsonl"
            ws.out_dir.mkdir(parents=True, exist_ok=True)
            existing: dict[str, dict] = {}
            if corpus_path.exists():
                for line in corpus_path.read_text().splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if row.get("case_id"):
                        existing[row["case_id"]] = row
            for c in cases:
                if c.get("case_id"):
                    existing[c["case_id"]] = c
            corpus_path.write_text(
                "\n".join(json.dumps(r, sort_keys=True) for r in existing.values())
                + ("\n" if existing else "")
            )
            _ssot_upsert_cases(ws, cases)  # PERSIST-3a: the SSOT cases table (one DB selector)

            # ONE AuditRecord — the audit IS the product (§2B).
            path_desc = (
                "NATIVE eval-case rows (verbatim, no transform)"
                if native
                else f"{'hand-authored' if hand_authored else 'REUSED' if reused else 'generated+pinned'} "
                f"mapping {mapping_id}"
            )
            actor_resolved = _resolve_actor(x_actor, actor)
            AuditLog(db_path=db_path).record(
                AuditRecord(
                    actor=actor_resolved,
                    action="ingest",
                    target=Target(type="corpus", id=ag_name),
                    why={
                        "rationale": f"ingested {len(cases)} cases via {path_desc}; "
                        f"normalized source→transcript on {normalized} case(s)"
                    },
                    before=None,
                    after={
                        "mapping_id": mapping_id,
                        "count": len(cases),
                        "corpus": str(corpus_path),
                        "case_ids": [c.get("case_id") for c in cases],
                    },
                )
            )
            return {
                "cases": cases, "mapping_id": mapping_id, "count": len(cases),
                "labeled": labeled, "normalized_source": normalized, "reused": reused,
                "native": native,
            }

        # REPRO-1 R1a (before ANY mapper touch): rows that already ARE eval cases import
        # verbatim — deep-copied so the source sample is never aliased into the corpus.
        native_rows = _native_eval_rows(sample)
        if native_rows is not None:
            return _finalize(
                [json.loads(json.dumps(r)) for r in native_rows], native=True
            )

        # CRITERIA-AWARE INGEST (gap #4): the extraction target is THIS agent's evaluation criteria,
        # not a fixed envelope. Derive the in-case fields its verification_contracts ground against
        # (the floor's oracle, e.g. patient_profile.conditions); require them at BOTH gates AND name
        # them in the rules the generator authors against. Graceful: an unresolvable ontology falls
        # back to () — the §4.1 behavior — so ingestion never gets worse than before.
        req_fields: tuple[str, ...] = ()
        try:
            _ag = _load_agent(ag_name, db_path)
            _ont_path, _ = _resolve_ontology_path(_ag, workdir)
            req_fields = required_case_fields(load_ontology(_ont_path))
        except Exception:  # noqa: BLE001 — criteria-targeting is best-effort; never break ingest
            req_fields = ()
        # expected_count = the number of source entries the transform must yield one case each
        # from. RESOLUTION ORDER (NARR-7 / G3 — the {issues,comments}-dict bug fix):
        #   1. an EXPLICIT expected_count (the connector / a precise caller names it);
        #   2. an ITERATED-COLLECTION HINT in extraction_rules — a backtick-quoted top-level key
        #      whose value is a list (e.g. "one case per `comments`") → len(dump[key]); this is the
        #      AGENT channel, since the SDK-MCP tool schema is frozen (no expected_count knob);
        #   3. the StoryWorld enhanced_scenes count (UNCHANGED default);
        #   4. a bare top-level list length, else 1.
        # Without (1) or (2) a non-list dict (e.g. {issues,comments}) infers 1 and a multi-record
        # transform is correctly REJECTED (the gate, not a silent mis-count) — see G3/R5.
        if expected_count is None:
            expected_count = _infer_iterated_count(sample, extraction_rules)
        rules = extraction_rules or (
            "Normalize this JSON dump into a per-entry array of eval cases; emit one record per "
            "source entry with at least case_id, response (the graded content), and context (the "
            "input the response was produced/graded against — e.g. the transcript/prompt/source "
            "text). A record with an empty context is rejected (the response would be graded "
            "against nothing)."
        )
        if req_fields:
            rules = rules + (
                " In ADDITION, each record MUST populate these evaluation-criteria fields the grader "
                "grounds against (nested dotted paths into the case; map them from the source JSON): "
                + ", ".join(req_fields)
                + ". A record missing any of these is rejected."
            )

        # The JUTE mapper is an OPT-IN add-on at a CONFIGURABLE url (_jute_base_url():
        # LITHRIM_JUTE_URL → the etlp_jute manifest default). In Docker localhost:3031 is the BFF
        # container itself, so a host/compose/remote mapper is only reachable via the override.
        client = EtlpJuteClient(base_url=_jute_base_url())
        # Honest front-door probe: a down mapper must say so — never surface as a bare 500 or the
        # misleading "extractor did not converge". `health()` never raises; test fakes without it
        # (getattr-guarded) skip the probe.
        _health = getattr(client, "health", None)
        if callable(_health) and not _health():
            raise RuntimeError(
                f"the JUTE mapper is not reachable at {getattr(client, 'base', _jute_base_url())} "
                "— ingest needs it to gate the transform. Start the bundled mapper "
                "(`docker compose up` includes it) or point LITHRIM_JUTE_URL at a running one. "
                "Grading and replay do not need the mapper."
            )

        # 3-WAY transform selection (INGEST-TEMPLATE-1 prepends (1) to the NARR-7.1 reuse/gen pair):
        #   (1) KNOWN SHAPE → a hand-authored, DETERMINISTIC curated JUTE template (labels carried
        #       BY CONSTRUCTION) — still live-gated on THIS sample before use;
        #   (2) REUSE a pinned transform if it still satisfies the invariant on this sample;
        #   (3) LM-GEN for a NOVEL shape (the unchanged generate→refine→pin path).
        # Each falls through to the next only when it leaves `template` None.
        reused = False
        hand_authored = False
        template = scored = mapping_id = None

        # (0) COMMIT (front door): the human APPROVED this exact template in preview — skip the 3-way
        # selection + any LM gen, just re-gate it on the data and (idempotently) pin it. The pin is the
        # only side-effect; the corpus upsert + audit are below, under commit_corpus.
        if approved_template is not None:
            scored = score_extraction(
                client, approved_template, sample,
                expected_count=expected_count, required_fields=req_fields,
            )
            if not scored["accepted"]:
                raise RuntimeError(
                    f"the approved transform failed the apply-time invariant "
                    f"(count={scored['count']}, nulls={scored['nulls']}); nothing pinned"
                )
            template = approved_template
            if pin_template:
                mapping_id = client.persist_or_update(f"ingest-{ag_name}", template).get("id")

        # (1) KNOWN SHAPE — a curated template for a recognized source shape, preferred over
        # REUSE/LM-gen. STILL live-gated (score_extraction on THIS sample): a near-miss variant that
        # does not accept leaves `template` None → falls through. PIN it (idempotent) so the corpus is
        # resolvable + auditable exactly like the reuse/gen paths.
        if template is None:
            _known = _known_shape_template(sample)
            if _known is not None:
                _k = score_extraction(
                    client, _known, sample,
                    expected_count=expected_count, required_fields=req_fields,
                )
                if _k["accepted"]:
                    template, scored = _known, _k
                    if pin_template:
                        mapping_id = client.persist_or_update(f"ingest-{ag_name}", _known).get("id")
                    hand_authored = True

        # (2) REUSE (NARR-7.1, generate-at-authoring → pin → REUSE): if a transform is ALREADY pinned
        # for this agent AND it still satisfies the structural invariant on THIS sample (the source
        # shape is unchanged), apply it deterministically and SKIP generation — $0, instant, NO LM. A
        # shape change fails the invariant → fall through to (re)generate+pin. Self-validating: a
        # mis-applying pin is NEVER reused (a mis-join returns null → not accepted). Only the FIRST
        # ingest of a shape pays the generation cost; a repeat "pull" is instant.
        # graceful: a client that can't list mappings (a minimal/test stub) simply can't reuse →
        # falls through to generate. Reuse is an optimization, never a requirement.
        if template is None:
            _find = getattr(client, "find_mapping_by_title", None)
            try:
                _existing = _find(f"ingest-{ag_name}") if callable(_find) else None
            except Exception as _reuse_exc:  # noqa: BLE001
                # CE-INGEST-RESILIENT-1: reuse is an OPTIMIZATION, never a requirement. A mapper
                # that can't list/lookup mappings (a 500 on GET /mappings — e.g. a poisoned row
                # with non-JSON content) must fall THROUGH to LM-gen, not kill the ingest. The
                # docstring above promised this; the bare _find() call did not honor it.
                _log.warning("ingest reuse lookup failed, generating instead: %s", _reuse_exc)
                _existing = None
            if _existing and (_existing.get("content") or {}).get("yaml"):
                _pre = score_extraction(
                    client, _existing["content"]["yaml"], sample,
                    expected_count=expected_count, required_fields=req_fields,
                )
                if _pre["accepted"]:
                    template, scored, mapping_id, reused = (
                        _existing["content"]["yaml"],
                        _pre,
                        _existing.get("id"),
                        True,
                    )

        # (3) LM-GEN — runs only when neither the curated template nor a pinned reuse set one.
        if template is None:
            # live-gate at generation time: the loop scores every candidate against :3031 via
            # test_template (a :3031-down / non-compiling candidate scores 0 and never accepts).
            # for_extractor=True (NARR-7 / G1): the EXTRACTOR-only relational-JOIN grounding addendum
            # (the $reduce find-by-key idiom + the two join traps + the double-quote/`+`-concat quirks)
            # — what makes generation on a join-heavy NEW shape converge. The VALIDATOR excerpt is
            # untouched (R1 — _RUNTIME_NOTES is shared but the addendum is extractor-path-only).
            excerpt = render_dsl_excerpt(
                client.get_dsl_spec(), include_envelope_example=False, for_extractor=True
            )

            def make_gen():
                return build_extractor_generator(
                    client, excerpt, sample,
                    expected_count=expected_count, required_fields=req_fields,
                )

            # GEN-LM (NARR-7.1 / INGEST-LM-1): the generate->refine loop needs a DSPy LM to AUTHOR
            # the transform YAML (the live gate is :3031; the LM only writes YAML, never grades).
            # The BFF configures no global LM (the council builds its own per-role LMs), so
            # _build_authoring_lm() resolves the user's CONFIGURED provider — settings.lm (offline)
            # -> the configured chat litellm LM -> the configured grading LM (build_judge_lm) -> a
            # clear RuntimeError. The blind build_claude_cli_lm default is GONE (claude reachable
            # ONLY via an explicit byo-claude config). SCOPED to this call (dspy.context below) so
            # it never perturbs the council. INGESTION-ONLY; moat untouched. An injected predictor
            # (offline tests) short-circuits via settings.lm, so this stays $0/offline there.
            import dspy

            gen_lm = _build_authoring_lm()
            # n=2 (NARR-7.1): the within-generator refine loop (up to 3 iters, live-gated each) IS the
            # convergence mechanism — n is redundant INDEPENDENT restarts. BYO-Claude is ~13s/attempt,
            # so n=2 (one restart for insurance) keeps the interactive chat-ingest responsive
            # (~13-26s) vs n=3's ~40s+; a batch caller can pass a higher n later.
            # CE-INGEST-FASTFAIL: bound the generate→refine grind (up to n*max_iters live-
            # gated LM attempts, ~13s each on BYO-Claude) — without a bound a non-converging
            # BYO-JSON shape grinds ~2min before failing. On the bound we raise TimeoutError
            # into the handler's except path: nothing is pinned (the PIN is below this), no
            # audit row (the AuditLog write is on the success path). The dspy.context is set
            # INSIDE the worker thread (it is thread-local). worker-safe, not signal-based.
            def _extract():
                with dspy.context(lm=gen_lm):
                    return best_of_n_extractor(make_gen, rules, sample, n=2)

            pred = _run_bounded(_extract, _ingest_timeout_s())
            template = getattr(pred, "jute_transform", "") or ""
            if not getattr(pred, "accepted", False):
                raise RuntimeError(
                    f"the extractor did not converge to a clean {expected_count}-case transform "
                    f"(structural output-invariant unmet); nothing pinned"
                )
            # apply-time re-gate: confirm the accepted template still satisfies the invariant on apply.
            scored = score_extraction(
                client, template, sample,
                expected_count=expected_count, required_fields=req_fields,
            )
            if not scored["accepted"]:
                raise RuntimeError(
                    f"the pinned transform failed the apply-time invariant "
                    f"(count={scored['count']}, nulls={scored['nulls']}); nothing pinned"
                )
            # PIN the converged transform as an etlp mapping (idempotent persist_or_update).
            # PREVIEW (pin_template=False) generates + gates the template but pins NOTHING.
            if pin_template:
                pin = client.persist_or_update(f"ingest-{ag_name}", template)
                mapping_id = pin.get("id")

        # INGEST-LABELS-1 + FLOOR-SOURCE-1 + preview/commit + audit all live in _finalize
        # (shared with the native path above).
        return _finalize(
            scored["cases"],
            template=template,
            mapping_id=mapping_id,
            reused=reused,
            hand_authored=hand_authored,
        )

    # ── CE-INGEST-FRONTDOOR-1: the first-class data front door (JSON/JSONL/CSV → preview → commit).
    def _decode_for_ingest(raw: str, fmt: str, filename: str, extraction_rules: str):
        """Decode an uploaded blob and derive the engine inputs: the JSON sample (as a string,
        the engine's interface), the expected row count, and an iterated-collection rules hint for
        the wrapped JSONL/CSV shapes (parse-in-Python, map-in-JUTE)."""
        from lithrim_bench.verification.ingest_decode import decode_records

        dec = decode_records(raw, fmt=fmt, filename=filename)
        rules = extraction_rules
        if dec.iterated_collection and not extraction_rules:
            rules = f"Emit one eval case per entry of the `{dec.iterated_collection}` collection."
        return dec, json.dumps(dec.sample), rules

    def _ingest_preview(
        raw: str, fmt: str = "auto", filename: str = "", extraction_rules: str = "", agent: str = ""
    ) -> dict:
        """PREVIEW: decode + select/generate a JUTE template + apply it to the data, returning the
        extracted cases + the template for the human to validate. Pins NOTHING, writes NO corpus."""
        dec, sample_json, rules = _decode_for_ingest(raw, fmt, filename, extraction_rules)
        res = _ingest_cases(
            sample_json, extraction_rules=rules, agent=agent,
            expected_count=dec.expected_count, pin_template=False, commit_corpus=False,
        )
        res["fmt"] = dec.fmt
        res["columns"] = dec.columns
        res["expected_count"] = dec.expected_count
        res["sample_cases"] = res["cases"][:5]  # a peek; `count` is the full total
        return res

    def _ingest_commit(
        approved_template: str | None, raw: str, fmt: str = "auto", filename: str = "",
        extraction_rules: str = "", agent: str = "",
    ) -> dict:
        """COMMIT: re-gate the human-APPROVED template on the data, pin it, and upsert the corpus —
        no LM generation. The decode is deterministic, so it reproduces the previewed cases."""
        _dec, sample_json, rules = _decode_for_ingest(raw, fmt, filename, extraction_rules)
        return _ingest_cases(
            sample_json, extraction_rules=rules, agent=agent,
            expected_count=_dec.expected_count, approved_template=approved_template,
            pin_template=True, commit_corpus=True,
        )

    # ── KB-CONTEXT-1: the honest read-only KB context aid (retrieve + show; NEVER a verdict).
    def _kb_context(query: str, namespace: str = "hipaa", top_k: int = 3) -> list[dict]:
        # Read-only retrieval over KbRagTool (GET :8002/v1/kb/{ns}/search). The kb:read key is read
        # from the BFF env (LITHRIM_KB_API_KEY / LITHRIM_API_KEY) by KbRagTool — secrets via env,
        # never the config plane. NO conforms/suppress here: it returns chunks to SHOW, and can
        # never change a verdict (kb_grounding-as-suppress over-clears these flags — measured).
        from lithrim_bench.verification import KbRagTool

        return KbRagTool().search(namespace, query, top_k=int(top_k))

    # ── META-VERDICT-1: the conversational "record my clinician verdict" WRITE — an immutable
    # AuditRecord (action=meta_verdict, target=verdict/run_id) via the FROZEN audited endpoint.
    def _record_meta_verdict(
        run_id: str,
        human_verdict: str,
        agrees_with_council: bool,
        judge_fallacy_code: str | None = None,
        rationale: str = "",
    ) -> dict:
        # Validate at the model boundary (an out-of-enum code raises ValidationError, surfaced by
        # the handler), then call the endpoint fn directly with every Depends/Header passed
        # explicitly (S-BS-82: no FastAPI sentinel leaks). $0 — no paid knob exists on this path.
        body = MetaVerdictRequest(
            run_id=run_id,
            human_verdict=human_verdict,
            agrees_with_council=agrees_with_council,
            judge_fallacy_code=judge_fallacy_code,
            rationale=rationale,
        )
        return post_meta_verdict_endpoint(
            body=body, db_path=db_path, default_actor=actor, x_actor=x_actor
        )

    return ToolContext(
        author_judge=_author_judge,
        get_judge=_get_judge,
        run_eval_replay=_run_eval_replay,
        get_agent=_get_agent,
        author_flag=_author_flag,
        review_runs=_review_runs,
        run_eval_pack=_run_eval_pack,
        assemble_agent=_assemble_agent,
        delete_judge=_delete_judge,
        create_flag=_create_flag,
        delete_flag=_delete_flag,
        put_grounding_contract=_put_grounding_contract,
        kb_context=_kb_context,
        ingest_cases=_ingest_cases,
        ingest_preview=_ingest_preview,
        ingest_commit=_ingest_commit,
        list_cases=_list_cases,
        record_meta_verdict=_record_meta_verdict,
        default_agent=req_agent,
        active_case=active_case,
        load_case_full=_load_case_full,
        known_case_ids=_known_case_ids,
    )


@app.post("/v1/chat")
async def chat_endpoint(
    req: ChatRequest,
    db_path: Path = Depends(get_config_db),
    out_dir: Path | None = Depends(get_out_dir),
    workdir: Path = Depends(get_ontology_workdir),
    collections_db: Path = Depends(get_collections_db),
    default_actor: Actor = Depends(get_actor),
    x_actor: str | None = Header(None, alias="X-Actor"),
) -> StreamingResponse:
    """The conversational-shell agent loop (UAP-5b / R11): host ClaudeSDKClient over
    the in-process SDK-MCP tools (the CORE author/read/REPLAY spine) and STREAM the
    multi-turn loop to the shell chat pane as SSE. BYO-Claude (local ``claude`` CLI /
    desktop auth — no API key; proven in D0). Every tool-call that writes config goes
    through the existing audited path → **the conversation IS the audit log** (R0).

    The SDK is loaded LAZILY by the loop (A5 — not at app import). Event frames are
    ``data: <json>\\n\\n`` (assistant_delta / tool_call / tool_result-as-gen-UI-part /
    error / done). A-SAFE: no tool can fire a paid run; the loop's ``run_eval`` is
    replay-only ($0), and the loop's own Claude calls are the human's BYO subscription.
    """
    from agent import run_chat, sse_format  # lazy: SDK loads here, on a real chat only

    actor = _resolve_actor(x_actor, default_actor)
    # CONV-UX-1 (W0): coerce a stale/invalid agent (e.g. a ws0_default literal in a
    # demo-clinical workspace) to the active workspace's agent; a valid one is honored.
    resolved_agent = _resolve_chat_agent(req.agent, db_path)
    # CHAT-CASE-RESOLVE-1: the case the human NAMED in the message wins (the explicit name is the
    # intent) — resolved DETERMINISTICALLY here so the grade targets it regardless of the model's
    # tool-calling; with no named case, fall back to the client's active_case (byte-identical).
    resolved_case = _resolve_named_case(req.message) or req.active_case
    ctx = _build_tool_context(
        resolved_agent, db_path, out_dir, workdir, collections_db, actor, x_actor,
        active_case=resolved_case,  # NARR-CHAT-LOOP / CHAT-CASE-RESOLVE-1: the shared active case
    )

    # ONB-0: text-only prior turns, replayed as context (folded into the loop's query preamble)
    history = [t.model_dump() for t in req.history]

    async def _events():
        async for event in run_chat(req.message, ctx, history=history):
            yield sse_format(event)

    return StreamingResponse(
        _events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/v1/connector/config")
def connector_config_endpoint(
    req: ConnectorConfigRequest,
    default_actor: Actor = Depends(get_actor),
    x_actor: str | None = Header(None, alias="X-Actor"),
) -> dict:
    """NARR-6 P1a: configure the StoryWorld admin connector. Run a READ-ONLY Test (GET
    ``/api/admin/sessions?limit=1``) with the supplied key; on a clean 200, write the key
    ONLY to the gitignored ``out/workspaces/<active>/.connector_env`` (§8.2; mirrors
    ``grade.py:_load_env``) + persist ``base_url`` + ``last_tested`` to a gitignored
    ``connector.json`` sidecar. The key is NEVER returned, logged, or written to SQLite/
    the manifest. On 401/timeout the status is surfaced and the key is NOT written.
    """
    from lithrim_bench.verification import StoryWorldAdminClient

    ws = workspace.get_active_workspace()
    client = StoryWorldAdminClient(req.base_url, api_key=req.x_api_key)
    test = client.test_connection()
    status, ok = int(test.get("status", 0)), bool(test.get("ok"))

    if not ok:
        # surface the failing status; do NOT write the key (non-vacuous vs the clean path)
        return {
            "connector_id": req.connector_id,
            "base_url": req.base_url,
            "status": status,
            "last_tested": None,
            "error": f"connection test failed (status {status})",
        }

    last_tested = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    ws.dir.mkdir(parents=True, exist_ok=True)
    # the key → .connector_env ONLY (gitignored, never SQLite/manifest/git/the response)
    (ws.dir / _CONNECTOR_ENV_NAME).write_text(f"{_STORYWORLD_KEY_VAR}={req.x_api_key}\n")
    # base_url + last_tested → the gitignored sidecar (NOT the Workspace dataclass)
    (ws.dir / _CONNECTOR_SIDECAR_NAME).write_text(
        json.dumps(
            {
                "connector_id": req.connector_id,
                "base_url": req.base_url,
                "last_tested": last_tested,
            },
            indent=2,
        )
        + "\n"
    )
    actor = _resolve_actor(x_actor, default_actor)
    AuditLog(db_path=ws.config_db).record(
        AuditRecord(
            actor=actor,
            action="connector_config",
            target=Target(type="connector", id=req.connector_id),
            why={"rationale": f"configured + tested the {req.connector_id} connector (status 200)"},
            before=None,
            after={"base_url": req.base_url, "last_tested": last_tested},  # NEVER the key
        )
    )
    return {
        "connector_id": req.connector_id,
        "base_url": req.base_url,
        "status": status,
        "last_tested": last_tested,
    }


# CE-PROVIDER-BACKEND (Build A) ────────────────────────────────────────────────────────────────
# Per-role OpenAI model keys (mirrors judges_dspy._OPENAI_ROLE_MODEL — kept local so app.py stays
# council-import-free). A config without `role` sets all three; with `role` only that judge's model.
_PROVIDER_OPENAI_ROLE_MODEL = {
    "risk_judge": "OPENAI_MODEL_RISK",
    "policy_judge": "OPENAI_MODEL_POLICY",
    "faithfulness_judge": "OPENAI_MODEL_FAITHFULNESS",
}
# Azure: a per-role DEPLOYMENT name (``model`` carries the deployment, not a model id). Mirrors
# runtime/council/judges_dspy._ROLE_DEPLOYMENT — the heterogeneous trio (risk→GPT, policy→Mistral,
# faithfulness→Llama) the owner runs. Set via Connect AI → Advanced; absent role → all three share it.
_PROVIDER_AZURE_ROLE_DEPLOYMENT = {
    "risk_judge": "AZURE_OPENAI_DEPLOYMENT_COUNCIL",
    "policy_judge": "AZURE_OPENAI_DEPLOYMENT_MISTRAL_LARGE_3",
    "faithfulness_judge": "AZURE_OPENAI_DEPLOYMENT_LLAMA_4_MAVERICK",
}
# Which env vars carry the SECRET per plane — these never leave .provider_env / os.environ.
_PROVIDER_SECRET_VARS = ("OPENAI_API_KEY", "AZURE_OPENAI_API_KEY", "ANTHROPIC_API_KEY")
# CONNECT-AI-CONSOLIDATE-1: the GLOBAL secret var per provider — the one a provider-level connect
# (Section 1, key entered once, NO role) writes, and the one a /v1/roles/bind reads back to REUSE the
# stored key (never re-keying). openai/azure/anthropic keep their existing global vars byte-identical;
# the broadened set gets a distinct namespaced var so openai vs openai_compatible never collide.
_PROVIDER_SECRET_VAR = {
    "openai": "OPENAI_API_KEY",
    "azure": "AZURE_OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "bedrock": "AWS_ACCESS_KEY_ID",
    "openai_compatible": "OPENAI_COMPATIBLE_API_KEY",
    "composo": "COMPOSO_API_KEY",  # F8-PROVIDER: the reward-model judge provider
}
# Where a provider stores its api_base/endpoint (azure / openai_compatible) so a role-bind can REUSE
# the already-stored endpoint — no re-endpointing. Other providers have no stored endpoint.
_PROVIDER_ENDPOINT_VAR = {
    "azure": "AZURE_OPENAI_ENDPOINT",
    "openai_compatible": "OPENAI_COMPATIBLE_API_BASE",
}

# PROVIDER-CENTER-A (S-BS-MR1a-CROSSPROVIDER): the GENERIC per-role binding (mirrors
# judges_dspy._ROLE_PROVIDER_KEYS — kept local so app.py stays council-import-free). When a grading
# config carries a `role`, ``_provider_env_vars`` writes these four vars so ``build_judge_lm``'s
# per-role provider override fires for that judge — the cross-provider-per-role unlock (risk→OpenAI,
# policy→Gemini, faithfulness→Anthropic coexist). The api_key var is the per-role SECRET.
_PROVIDER_ROLE_BINDING = {
    "risk_judge": {
        "provider": "LITHRIM_LLM_PROVIDER_RISK", "model": "LITHRIM_LLM_MODEL_RISK",
        "api_key": "LITHRIM_LLM_API_KEY_RISK", "api_base": "LITHRIM_LLM_API_BASE_RISK",
        "api_version": "LITHRIM_LLM_API_VERSION_RISK",
    },
    "policy_judge": {
        "provider": "LITHRIM_LLM_PROVIDER_POLICY", "model": "LITHRIM_LLM_MODEL_POLICY",
        "api_key": "LITHRIM_LLM_API_KEY_POLICY", "api_base": "LITHRIM_LLM_API_BASE_POLICY",
        "api_version": "LITHRIM_LLM_API_VERSION_POLICY",
    },
    "faithfulness_judge": {
        "provider": "LITHRIM_LLM_PROVIDER_FAITHFULNESS", "model": "LITHRIM_LLM_MODEL_FAITHFULNESS",
        "api_key": "LITHRIM_LLM_API_KEY_FAITHFULNESS", "api_base": "LITHRIM_LLM_API_BASE_FAITHFULNESS",
        "api_version": "LITHRIM_LLM_API_VERSION_FAITHFULNESS",
    },
}

# ── REPRO-1 R2a: the binding plane generalizes to ANY authored judge role (3→N). The v2 trio
# keeps its SHORT legacy env suffixes (back-compat with every existing .provider_env /
# role_bindings row); an authored role's suffix is its uppercased id. Role ids are validated at
# the request boundary (_ROLE_ID_PATTERN) so a suffix can never inject env-name garbage, and the
# lowercase restriction makes suffix→role inversion exact.
_LEGACY_ROLE_SUFFIX = {
    "risk_judge": "RISK", "policy_judge": "POLICY", "faithfulness_judge": "FAITHFULNESS",
}
_ROLE_BY_LEGACY_SUFFIX = {v: k for k, v in _LEGACY_ROLE_SUFFIX.items()}


def _role_env_suffix(role: str) -> str:
    return _LEGACY_ROLE_SUFFIX.get(role) or role.upper()


def _role_binding_env_names(role: str) -> dict[str, str]:
    """The 5 per-role binding env vars for ANY judge role (the generalized
    ``_PROVIDER_ROLE_BINDING`` row — that dict remains as the legacy-trio constant the
    one-time migration reads)."""
    s = _role_env_suffix(role)
    return {
        "provider": f"LITHRIM_LLM_PROVIDER_{s}", "model": f"LITHRIM_LLM_MODEL_{s}",
        "api_key": f"LITHRIM_LLM_API_KEY_{s}", "api_base": f"LITHRIM_LLM_API_BASE_{s}",
        "api_version": f"LITHRIM_LLM_API_VERSION_{s}",
    }


# var-name prefix → the role_bindings DB field, for splitting a flat env dict back into
# per-role rows (the api_key prefix is deliberately ABSENT — the secret stays file-only).
_DB_FIELD_BY_VAR_PREFIX = {
    "LITHRIM_LLM_PROVIDER_": "provider",
    "LITHRIM_LLM_MODEL_": "model",
    "LITHRIM_LLM_API_BASE_": "endpoint",
    "LITHRIM_LLM_API_VERSION_": "api_version",
}


def _role_field_from_var(var: str) -> tuple[str, str] | None:
    """Invert a per-role binding var name → (role, db_field); None for anything else (the
    secret key vars, the global selectors, the chat plane)."""
    for prefix, db_field in _DB_FIELD_BY_VAR_PREFIX.items():
        if var.startswith(prefix):
            suffix = var[len(prefix):]
            return (_ROLE_BY_LEGACY_SUFFIX.get(suffix) or suffix.lower()), db_field
    return None


def _assert_bindable_judge_role(role: str) -> None:
    """422 unless ``role`` is a reviewer the ACTIVE workspace's pack declares (production ∪
    lens roles — where a JudgeBuilder-authored role lands after its snapshot splice). The
    typo-guard: a model binding for a reviewer that cannot grade is refused, never silently
    stored."""
    from lithrim_bench.harness import pack as _pack_mod

    ws = workspace.get_active_workspace()
    selectable = set(_pack_mod.pack_production_judges(ws.pack)) | set(
        _pack_mod.pack_lenses(ws.pack)
    )
    if role not in selectable:
        raise HTTPException(
            status_code=422,
            detail=(
                f"unknown reviewer role {role!r} — this workspace offers "
                f"{sorted(selectable)} (create a new reviewer first, then bind it)"
            ),
        )
# The broadened grading provider set litellm speaks (PROVIDER-CENTER-A). These have NO global
# grading selector — they are per-role ONLY (require a `role`). ``anthropic`` is here for the GRADING
# plane (faithfulness→Anthropic, the mixed council); the assistant-plane anthropic stays global.
_PER_ROLE_ONLY_PROVIDERS = ("gemini", "bedrock", "openai_compatible", "anthropic", "composo")

# CONNECT-AI-AZURE-1: the council-default Azure api_version (lazy — keep app.py free of the [council]
# LM deps at module load). A bare BFF without the extra falls back to the literal default.
_DEFAULT_AZURE_API_VERSION = "2024-10-21"


def _settings_azure_api_version() -> str:
    """The council settings default ``AZURE_OPENAI_API_VERSION`` (lazy import; the literal fallback
    when the [council] extra is absent). The last-resort default for an azure path with no explicit
    or stored version — never an empty version (litellm requires one for azure)."""
    try:
        from lithrim_bench.runtime.council import settings as council_settings

        return council_settings.settings.AZURE_OPENAI_API_VERSION or _DEFAULT_AZURE_API_VERSION
    except Exception:  # noqa: BLE001 — the [council] extra may be absent in a bare BFF
        return _DEFAULT_AZURE_API_VERSION


def _stored_provider_api_version(provider: str) -> str | None:
    """Read a provider's already-stored Azure ``api_version`` back from .provider_env (the bind
    reuses it — no re-entry). Only azure stores one; other providers return None."""
    if provider != "azure":
        return None
    return _parse_env_file(_provider_env_path()).get("AZURE_OPENAI_API_VERSION") or None


def _provider_env_vars(req: ProviderConfigRequest) -> dict[str, str]:
    """Map a validated provider-config request to the env vars the council/chat planes read
    (settings.py + the chat-author provider). The api_key rides one of _PROVIDER_SECRET_VARS (global)
    or the per-role LITHRIM_LLM_API_KEY_<ROLE> (PROVIDER-CENTER-A); the rest (provider selector +
    model + endpoint) are non-secret. Raises ValueError on a missing required field so the endpoint
    surfaces a 400 BEFORE probing/writing.

    PROVIDER-CENTER-A: a grading config WITH a `role` ALSO writes the GENERIC per-role binding
    (LITHRIM_LLM_{PROVIDER,MODEL,API_KEY,API_BASE}_<ROLE>) so ``build_judge_lm``'s per-role override
    routes that judge to ANY provider — and a different role on a different provider coexists. The
    existing no-role/global openai+azure writes are BYTE-IDENTICAL (the per-role binding is additive,
    gated on `role`). gemini/bedrock/openai_compatible are per-role ONLY (no global selector)."""
    env: dict[str, str] = {}
    if req.plane == "grading":
        # PROVIDER-CENTER-A: the generic per-role binding (additive; only when a role is given).
        # R2a: ANY validated judge role id resolves (authored roles included), not just the trio.
        if req.role:
            binding = _role_binding_env_names(req.role)
            env[binding["provider"]] = req.provider
            if req.model:
                env[binding["model"]] = req.model
            env[binding["api_key"]] = req.api_key  # the per-role SECRET (write-only on .provider_env)
            if req.endpoint:  # azure / openai_compatible api_base
                env[binding["api_base"]] = req.endpoint
            if req.provider == "azure":
                # CONNECT-AI-AZURE-1: a per-role azure judge needs an api_version or litellm hits the
                # api-version / DeploymentNotFound wall. Reuse the request's version (the roles-bind
                # passes the STORED AZURE_OPENAI_API_VERSION in); fall back to the stored value, then
                # the council default — never an empty version.
                env[binding["api_version"]] = (
                    (req.api_version or "").strip()
                    or _stored_provider_api_version("azure")
                    or _settings_azure_api_version()
                )
        if req.provider == "openai":
            env["LITHRIM_LLM_PROVIDER"] = "openai"
            env["OPENAI_API_KEY"] = req.api_key
            if req.model:
                if req.role:
                    # R2a: only the legacy trio has a global-path OPENAI_MODEL_* var; an authored
                    # role rides SOLELY the generic per-role binding written above.
                    legacy_var = _PROVIDER_OPENAI_ROLE_MODEL.get(req.role)
                    if legacy_var:
                        env[legacy_var] = req.model
                else:
                    for var in _PROVIDER_OPENAI_ROLE_MODEL.values():
                        env[var] = req.model
        elif req.provider == "azure":
            if not req.endpoint:
                raise ValueError("provider='azure' requires `endpoint` (the Azure OpenAI endpoint)")
            env["LITHRIM_LLM_PROVIDER"] = "azure"
            env["AZURE_OPENAI_API_KEY"] = req.api_key
            env["AZURE_OPENAI_ENDPOINT"] = req.endpoint
            if req.api_version:  # CONNECT-AI-AZURE-1: additive — else the settings default stands
                env["AZURE_OPENAI_API_VERSION"] = req.api_version.strip()
            if req.model:  # the Azure DEPLOYMENT name (e.g. policy_judge → your Mistral deployment)
                if req.role:
                    # R2a: only the legacy trio has a global-path deployment var; an authored
                    # role rides SOLELY the generic per-role binding written above.
                    legacy_var = _PROVIDER_AZURE_ROLE_DEPLOYMENT.get(req.role)
                    if legacy_var:
                        env[legacy_var] = req.model
                else:
                    for var in _PROVIDER_AZURE_ROLE_DEPLOYMENT.values():
                        env[var] = req.model
        elif req.provider in _PER_ROLE_ONLY_PROVIDERS:
            # CONNECT-AI-CONSOLIDATE-1: a provider-level connect (Section 1 — key entered once, NO
            # role) now stores the provider's GLOBAL secret so a later /v1/roles/bind can REUSE it
            # (no re-keying). With a `role` the per-role binding above is still the live wiring; the
            # global secret is additive (the bind reads it back). openai_compatible still needs an
            # endpoint (stored as the provider's api_base for reuse).
            if req.provider == "openai_compatible" and not req.endpoint:
                raise ValueError(
                    "provider='openai_compatible' requires `endpoint` (the OpenAI-compatible api_base)"
                )
            env[_PROVIDER_SECRET_VAR[req.provider]] = req.api_key  # the GLOBAL stored key (reused at bind)
            endpoint_var = _PROVIDER_ENDPOINT_VAR.get(req.provider)
            if endpoint_var and req.endpoint:
                env[endpoint_var] = req.endpoint
        else:
            raise ValueError(
                f"provider={req.provider!r} is not a grading provider "
                f"(use openai|azure|gemini|bedrock|openai_compatible|composo)"
            )
    else:  # assistant plane
        # CONV-RUNTIME-1: the assistant (chat) plane is un-gated to the broadened provider set.
        # anthropic stays BYTE-IDENTICAL — ANTHROPIC_API_KEY + LITHRIM_CHAT_PROVIDER=anthropic — so
        # the Agent-SDK / BYO-Claude chat path keeps working. Any OTHER provider writes the chat
        # env-var contract LITHRIM_CHAT_{PROVIDER,MODEL,API_KEY[,API_BASE]} the litellm conversation
        # loop reads (the api_key is the chat SECRET, write-only on .provider_env, never echoed).
        if req.provider == "anthropic":
            env["LITHRIM_CHAT_PROVIDER"] = "anthropic"
            env["ANTHROPIC_API_KEY"] = req.api_key
        else:
            if not req.model:
                raise ValueError(
                    f"the assistant plane provider {req.provider!r} requires `model` (the chat model)"
                )
            if req.provider in ("azure", "openai_compatible") and not req.endpoint:
                raise ValueError(
                    f"the assistant plane provider {req.provider!r} requires `endpoint` (the api_base)"
                )
            env["LITHRIM_CHAT_PROVIDER"] = req.provider
            env["LITHRIM_CHAT_MODEL"] = req.model
            env["LITHRIM_CHAT_API_KEY"] = req.api_key  # the chat SECRET (write-only on .provider_env)
            if req.endpoint:  # azure / openai_compatible api_base
                env["LITHRIM_CHAT_API_BASE"] = req.endpoint
            if req.provider == "azure":
                # CONNECT-AI-AZURE-1: an azure chat needs an api_version (litellm wall). Reuse the
                # request's version (the roles-bind passes the STORED one in); fall back to the stored
                # value, then the council default — never an empty version.
                env["LITHRIM_CHAT_API_VERSION"] = (
                    (req.api_version or "").strip()
                    or _stored_provider_api_version("azure")
                    or _settings_azure_api_version()
                )
    return env


def _probe_provider(
    *, plane, provider, api_key, endpoint=None, model=None, role=None, api_version=None
) -> dict:
    """Read-only validate the key BEFORE any write (SPEC §3.1 step 1). A bounded 1-token completion
    on the SAME litellm/openai path build_judge_lm grades through (grading) / a cheap Anthropic ping
    (assistant). Returns ``{ok: bool, error?: str}``; NEVER raises (network/auth errors → ok=False).
    Patched in tests so the green bar is $0/offline (no live call). Lazy imports keep app.py free of
    the [council] LM deps at module load.

    CONNECT-AI-AZURE-1: for ``azure`` the litellm probe REQUIRES an ``api_version`` — without it the
    Azure probe itself fails (so a UI-only Azure connect / roles-bind re-probe never validated). The
    version defaults to ``settings.AZURE_OPENAI_API_VERSION`` when not threaded in. Non-azure
    providers never send it."""
    try:
        # CONV-RUNTIME-1: route the probe by PROVIDER, not by plane — a non-anthropic assistant
        # (the litellm chat) probes via the litellm branch below, exactly like a grading provider.
        # Only anthropic (either plane: the SDK chat / the mixed-council faithfulness seat) pings via
        # the anthropic SDK.
        if provider == "anthropic":
            import anthropic  # type: ignore

            client = anthropic.Anthropic(api_key=api_key)
            client.messages.create(
                # DRYRUN-2026-07-03: a CURRENT default (claude-3-5-haiku-latest is retired on
                # the live API — connecting Anthropic failed out of the box); ≥16 tokens.
                model=model or "claude-haiku-4-5-20251001",
                max_tokens=16,
                messages=[{"role": "user", "content": "ping"}],
            )
            return {"ok": True}
        if provider == "composo":
            # F8-PROVIDER: probe the SAME reward wire the judge grades through — a trivial
            # message pair scored against a trivial criterion. evaluate() raises unless a
            # numeric score comes back, so the ok gate is non-vacuous.
            from lithrim_bench.runtime.council.reward_lm import RewardModelLM

            RewardModelLM(api_key=api_key, api_base=endpoint).evaluate(
                "ping", "pong", "Reward any reply."
            )
            return {"ok": True}
        # grading plane — probe via litellm (the path dspy.LM uses under build_judge_lm).
        # PROVIDER-CENTER-A: the broadened types route by their litellm prefix (openai_compatible →
        # openai + an api_base; gemini/bedrock native). Default model per provider keeps the probe
        # bounded when none is given.
        import litellm  # type: ignore

        prefix = {
            "openai": "openai", "azure": "azure", "anthropic": "anthropic",
            "gemini": "gemini", "bedrock": "bedrock", "openai_compatible": "openai",
        }.get(provider, "openai")
        default_model = {
            "azure": "gpt-4.1", "gemini": "gemini-1.5-pro",
            "bedrock": "anthropic.claude-3-sonnet-v1", "anthropic": "claude-haiku-4-5-20251001",
        }.get(provider, "gpt-4o")
        # DRYRUN-2026-07-16: NO default model can be assumed on an arbitrary OpenAI-compatible
        # host (Featherless serves no gpt-4o, so the model-less UI connect always 404'd) —
        # discover candidates from the host's own /models listing and probe them in order. A
        # model-carrying probe (the roles-bind re-probe) never discovers; a failed listing
        # degrades to the single default-model attempt.
        candidates: list[str] = []
        if provider == "openai_compatible" and not model and endpoint:
            candidates = _discover_openai_compatible_models(endpoint, api_key)
        if model:
            candidates = [model]
        if not candidates:
            candidates = [default_model]
        # DRYRUN-2026-07-03: parameter-MINIMAL — reasoning-family models (gpt-5.5) reject a
        # temperature override AND a <16-token completion budget; the 1-token/temp-0 ping made
        # binding a valid frontier model fail with an opaque BadRequestError.
        last_exc: Exception | None = None
        for candidate in candidates:
            completion_kwargs = {
                "model": f"{prefix}/{candidate}",
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 16, "api_key": api_key,
            }
            if endpoint:  # azure / openai_compatible api_base
                completion_kwargs["api_base"] = endpoint
            if provider == "azure":  # CONNECT-AI-AZURE-1: the azure probe needs an api_version
                completion_kwargs["api_version"] = api_version or _settings_azure_api_version()
            try:
                litellm.completion(**completion_kwargs)
                return {"ok": True}
            except Exception as exc:  # noqa: BLE001
                # DRYRUN-2026-07-16 (Option A): an AUTH-shaped failure is a bad key — fail FAST,
                # never fall through to another public model (a bad key must never "pass" and get
                # stored). A model-shaped failure (gated/offline/not-found) just means THIS
                # candidate is unservable; try the next discovered one.
                if _is_auth_error(exc):
                    return {"ok": False, "error": _probe_error(exc, api_key)}
                last_exc = exc
        return {"ok": False, "error": _probe_error(last_exc, api_key) if last_exc else "unknown error"}
    except Exception as exc:  # noqa: BLE001 — any probe failure is a clean ok=False, not a 500
        return {"ok": False, "error": _probe_error(exc, api_key)}


# how many discovered models to try before giving up — bounds the worst-case probe cost (each
# attempt is a tiny 16-token completion; a valid key usually serves the first candidate).
_OPENAI_COMPATIBLE_PROBE_CANDIDATES = 5
_AUTH_ERROR_NAMES = frozenset({"AuthenticationError", "PermissionDeniedError"})


def _probe_error(exc: Exception, api_key: str) -> str:
    """CONNECT-AI-COMPAT-1: the probe's user-facing failure string. The class name leads (the
    pre-existing contract), then the provider's message so the user can tell WHY — one-line
    (fits the 400 detail), BOUNDED (never a traceback-sized blob), and with the secret redacted
    (a raw provider message can echo the api key back)."""
    msg = " ".join(str(exc).split())
    if api_key:
        msg = msg.replace(api_key, "***")
    out = f"{type(exc).__name__}: {msg}" if msg else type(exc).__name__
    return out[:250]


def _is_auth_error(exc: Exception) -> bool:
    """True iff ``exc`` looks like an authentication/authorization failure (a bad or unentitled
    key) rather than a model-shaped one. Matched by litellm/openai error class name OR an HTTP
    401/403 ``status_code`` — so the check holds without importing litellm's exception classes."""
    if type(exc).__name__ in _AUTH_ERROR_NAMES:
        return True
    return getattr(exc, "status_code", None) in (401, 403)


def _discover_openai_compatible_models(endpoint: str, api_key: str) -> list[str]:
    """Best-effort model ids from an OpenAI-compatible host's ``GET {api_base}/models`` (bounded to
    the first ``_OPENAI_COMPATIBLE_PROBE_CANDIDATES``). Never raises: a listing failure returns []
    so the probe degrades to the single default-model attempt. The listing alone does NOT validate
    the key (some hosts, e.g. Featherless, serve /models unauthenticated); the completion does."""
    try:
        import httpx  # type: ignore

        listing = httpx.get(
            endpoint.rstrip("/") + "/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        listing.raise_for_status()
        hosted = (listing.json() or {}).get("data") or []
        ids = [(row or {}).get("id") for row in hosted]
        return [mid for mid in ids if mid][:_OPENAI_COMPATIBLE_PROBE_CANDIDATES]
    except Exception:  # noqa: BLE001 — discovery is best-effort; the completion still gates the key
        return []


# ── ROLE-BINDINGS-DB: the non-secret per-role binding lives in the config DB, not .provider_env ──
# The api_key (the SECRET half) stays write-only on .provider_env; these four non-secret fields move
# to the role_bindings config table. Derived from _PROVIDER_ROLE_BINDING (the judge per-role env
# vars, minus the api_key) ⊕ the chat consumer — so it never drifts from the writer.
# SCOPE: the 3 JUDGE roles move to the DB. The chat_assistant binding stays file-based — loop.py (the
# conversational author, council/dspy-free) reads ``.provider_env`` directly and must not depend on the
# config DB; relocating the chat binding is a deliberate follow-up.
_ROLE_BINDING_DB_ENV: dict[str, dict[str, str]] = {
    role: {"provider": b["provider"], "model": b["model"], "endpoint": b["api_base"],
           "api_version": b["api_version"]}
    for role, b in _PROVIDER_ROLE_BINDING.items()
}
# var → (role, field), to split a flat env_vars dict back into per-role bindings.
_DB_ENV_TO_ROLE_FIELD: dict[str, tuple[str, str]] = {
    var: (role, field) for role, m in _ROLE_BINDING_DB_ENV.items() for field, var in m.items()
}


def _role_bindings_db_path() -> Path:
    """The config DB the per-role bindings live in — Postgres when ``LITHRIM_DB_URL`` is set, else a
    SQLite alongside the other provider sidecars (the durable ``/app/out`` volume in Docker). Resolved
    from ``_provider_env_path().parent`` so a test that redirects the sidecar redirects this too."""
    return _provider_env_path().parent / "provider_config.sqlite"


def _split_provider_env_vars(
    env_vars: dict[str, str],
) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    """Partition a flat provider env-var dict into ``(db_bindings: role → {field: val}, file_vars)``.
    The NON-SECRET per-role binding vars route to the DB; everything else (the api_key + the global
    provider config) stays write-only on ``.provider_env``."""
    db_bindings: dict[str, dict[str, str]] = {}
    file_vars: dict[str, str] = {}
    for key, val in env_vars.items():
        # R2a: pattern-inverted (any role's binding vars split correctly, authored roles
        # included) — _DB_ENV_TO_ROLE_FIELD remains as the legacy-trio constant.
        rf = _role_field_from_var(key)
        if rf is not None:
            role, field = rf
            db_bindings.setdefault(role, {})[field] = val
        else:
            file_vars[key] = val
    return db_bindings, file_vars


def _hydrate_role_bindings_into_env() -> None:
    """Set ``os.environ`` for every persisted role binding (the per-role binding vars the grade
    reads). Called at startup AFTER the ``.provider_env`` load so a grade sees the chosen model."""
    from lithrim_bench.harness import role_bindings as _rb

    for role, binding in _rb.load_bindings(db_path=_role_bindings_db_path()).items():
        # R2a: derive the env names for ANY stored role (authored roles hydrate too).
        names = _role_binding_env_names(role)
        env_map = {
            "provider": names["provider"], "model": names["model"],
            "endpoint": names["api_base"], "api_version": names["api_version"],
        }
        for field, var in env_map.items():
            if binding.get(field) is not None:
                os.environ[var] = binding[field]


def _migrate_provider_env_bindings_to_db() -> None:
    """One-time carry-forward: if the ``role_bindings`` DB is empty but ``.provider_env`` holds legacy
    per-role binding vars, import them into the DB and STRIP the non-secret vars from the file (the
    keys + global provider config stay). Idempotent — a populated DB is a no-op, so nothing is lost on
    the cut-over and re-runs do nothing."""
    from lithrim_bench.harness import role_bindings as _rb

    db_path = _role_bindings_db_path()
    if _rb.load_bindings(db_path=db_path):  # already migrated / authored → no-op
        return
    env = _parse_env_file(_provider_env_path())
    file_vars = dict(env)
    migrated = False
    for role, env_map in _ROLE_BINDING_DB_ENV.items():
        binding = {field: env[var] for field, var in env_map.items() if env.get(var)}
        if binding.get("provider"):  # a real legacy binding for this role
            _rb.save_binding(role, binding, db_path=db_path)
            migrated = True
            for var in env_map.values():  # remove the non-secret binding vars from the file
                file_vars.pop(var, None)
    if migrated:
        _write_sidecar(_provider_env_path(), "".join(f"{k}={v}\n" for k, v in file_vars.items()))


def _persist_and_reload_provider(env_vars: dict[str, str]) -> None:
    """SPEC §3.1 steps 2-4: WRITE-ONLY the provider env vars to the gitignored repo-root
    ``.provider_env`` (merging with any prior plane's vars so a grading + an assistant key coexist),
    set ``os.environ`` (subprocess grades inherit it at spawn), and REFRESH the in-process council
    ``settings`` singleton IN PLACE so ``build_judge_lm`` reads the new key with NO restart. The
    singleton is mutated in place (not reassigned) because every consumer did ``from .settings import
    settings`` — a holder of the object, not the module attribute — so a reassignment would not reach
    them; setting attributes on the live object does.

    PROVIDER-CENTER-A: the LIVE object is mutated and the module attr is REPOINTED back to that SAME
    object (it is NOT swapped for a fresh ``Settings()``). The earlier reassign orphaned the holders
    after the FIRST call — so a SECOND per-role bind (the cross-provider council: role A→gemini, then
    role B→openai) mutated a fresh object the holders no longer referenced, silently breaking the
    no-restart guarantee. To still pick up env keys not in ``env_vars`` (other planes), a throwaway
    ``Settings()`` is read from env and its declared fields are copied ONTO the live holder in place."""
    # 2) ROLE-BINDINGS-DB split: the NON-SECRET per-role binding → the config DB (role_bindings);
    #    the key + the global provider config → .provider_env (write-only, never the DB).
    db_bindings, file_vars = _split_provider_env_vars(env_vars)
    if file_vars:
        merged = _parse_env_file(_provider_env_path())
        merged.update(file_vars)
        _write_sidecar(_provider_env_path(), "".join(f"{k}={v}\n" for k, v in merged.items()))
    if db_bindings:
        from lithrim_bench.harness import role_bindings as _rb

        db_path = _role_bindings_db_path()
        existing = _rb.load_bindings(db_path=db_path)
        for role, fields in db_bindings.items():
            _rb.save_binding(role, {**(existing.get(role) or {}), **fields}, db_path=db_path)
    # 3) os.environ → inherited by the next subprocess grade (the binding + the key, both, unchanged)
    for key, val in env_vars.items():
        os.environ[key] = val
    # 4) refresh the in-process council settings singleton with NO restart
    try:
        from lithrim_bench.runtime.council import settings as council_settings

        live = council_settings.settings
        # copy a fresh env-read of EVERY declared field onto the live holder in place (picks up env
        # keys outside env_vars, e.g. another plane's), then overlay the explicit env_vars (coerced).
        fresh = council_settings.Settings()
        for field in type(live).model_fields:
            setattr(live, field, getattr(fresh, field))
        for key, val in env_vars.items():
            if hasattr(live, key):
                _coerce_set(live, key, val)
        council_settings.settings = live  # repoint to the SAME object the holders reference
    except Exception:  # noqa: BLE001 — the [council] extra may be absent in a bare BFF; env still set
        pass


def _coerce_set(obj, key: str, raw: str) -> None:
    """Set ``obj.key = raw`` coercing to the field's declared type (bool/int) so a string from the
    env file round-trips into the pydantic-typed council Settings without a validation surprise."""
    current = getattr(obj, key)
    if isinstance(current, bool):
        setattr(obj, key, raw.strip().lower() in ("1", "true", "yes", "on"))
    elif isinstance(current, int) and not isinstance(current, bool):
        try:
            setattr(obj, key, int(raw))
        except ValueError:
            setattr(obj, key, raw)
    else:
        setattr(obj, key, raw)


def _read_provider_status() -> dict:
    """Read the gitignored ``.provider_status.json`` non-secret sidecar (provider/model/endpoint/
    last_tested per plane). Absent → both planes unconfigured. NEVER carries a key."""
    base = {"grading": {"configured": False}, "assistant": {"configured": False}}
    status_path = _provider_status_path()
    if status_path.exists():
        try:
            stored = json.loads(status_path.read_text())
            for plane in ("grading", "assistant"):
                if plane in stored:
                    base[plane] = stored[plane]
        except (json.JSONDecodeError, OSError):
            pass
    return base


# MODEL-REGISTRY-1a (SPEC_COMMUNITY_EDITION §8) ─────────────────────────────────────────────────
# A configured model is a first-class, reusable, CAPABILITY-AWARE entity, decoupled from the judge
# role (the LiteLLM ``model_list`` pattern). Capabilities — esp. ``logprobs`` — are the load-bearing
# differentiator (OpenAI yes → calibrated confidence; Claude / Mistral-via-Azure no → confidence
# dark), surfaced at pick time. The catalog = curated presets + a ``capabilities_for`` family-infer
# so a CUSTOM (non-preset) model still gets an honest flag; Azure is deployment-name-based (no model
# catalog applies — it's the user's deployments). The registry REUSES Build A's env mechanism: the
# key is write-only on ``.provider_env``; a role binds via the same ``_provider_env_vars`` +
# ``_persist_and_reload_provider`` path ``build_judge_lm`` reads. The frozen council is untouched.

# Curated per-provider presets, each capability-annotated. A small HONEST map — names are cosmetic,
# the capabilities are the product. ``logprobs`` gates the calibrated-confidence read.
_MODEL_CATALOG_PRESETS: dict[str, list[dict]] = {
    "openai": [
        {"model": "gpt-4o", "logprobs": True, "context_window": 128000, "cost_tier": "mid"},
        {"model": "gpt-4o-mini", "logprobs": True, "context_window": 128000, "cost_tier": "low"},
        {"model": "gpt-4.1", "logprobs": True, "context_window": 1000000, "cost_tier": "mid"},
        # o-series reasoning models do not return token logprobs → confidence dark
        {"model": "o3-mini", "logprobs": False, "context_window": 200000, "cost_tier": "mid"},
    ],
    "anthropic": [
        {"model": "claude-3-5-sonnet-latest", "logprobs": False, "context_window": 200000,
         "cost_tier": "mid"},
        {"model": "claude-3-5-haiku-latest", "logprobs": False, "context_window": 200000,
         "cost_tier": "low"},
    ],
}
# Azure has no model catalog — it's deployment-name-based (bring YOUR deployment). Kept as an explicit
# empty-list-plus-note so the UI renders an honest "type your deployment" affordance, not a wall.
_MODEL_CATALOG_AZURE_NOTE = (
    "deployment-name-based — Azure has no model catalog; register your deployment name as the "
    "`model` (e.g. your gpt-4.1 / Mistral / Llama deployment)."
)


def capabilities_for(provider: str, model: str) -> dict:
    """Infer a model's capabilities by family so a CUSTOM (non-preset) model still gets an HONEST
    ``logprobs`` flag — the differentiated-catalog point. A preset hit returns its curated row;
    otherwise the family heuristic decides. OpenAI ``gpt-*`` (non-reasoning) → logprobs True;
    ``o*`` reasoning → False; Anthropic ``claude-*`` → False; Azure → deployment-based (unknown →
    conservatively False, the user can't rely on logprobs from an arbitrary deployment)."""
    provider = (provider or "").strip().lower()
    name = (model or "").strip().lower()
    for preset in _MODEL_CATALOG_PRESETS.get(provider, []):
        if preset["model"].lower() == name:
            return {k: preset[k] for k in ("logprobs", "context_window", "cost_tier")}
    if provider == "openai":
        # gpt-* return token logprobs; o-series reasoning models do not.
        logprobs = name.startswith("gpt-") or name.startswith("gpt")
        if name.startswith("o1") or name.startswith("o3") or name.startswith("o4"):
            logprobs = False
        return {"logprobs": bool(logprobs), "context_window": None, "cost_tier": "unknown"}
    if provider == "anthropic":
        return {"logprobs": False, "context_window": None, "cost_tier": "unknown"}
    # azure / anything else: deployment-based — don't promise logprobs we can't guarantee
    return {"logprobs": False, "context_window": None, "cost_tier": "unknown"}


# MODEL-REGISTRY-1b (SPEC §8 — "the catalog = presets + custom + live"): the LIVE axis. For the
# providers that expose a ``/models`` API (OpenAI, Anthropic) we fetch the live list with the
# ALREADY-CONFIGURED key (read server-side from ``.provider_env`` — never a query param, never the
# response, never logged), annotate each via ``capabilities_for``, and merge with the presets.
# Azure is deployment-name-based → never fetched.
def _is_openai_chat_model(model_id: str) -> bool:
    """The OpenAI chat-model filter: KEEP ``gpt-*`` / ``o1*``/``o3*``/``o4*`` / ``chatgpt-*``; DROP
    embeddings / whisper / tts / dall-e / moderation / ``text-*`` (and the legacy completion
    families). ``text-*`` is dropped first so ``text-embedding-*`` / ``text-moderation-*`` can never
    sneak in via a ``gpt`` substring."""
    name = (model_id or "").strip().lower()
    if name.startswith("text-"):
        return False
    if any(name.startswith(bad) for bad in
           ("whisper", "tts", "dall-e", "dalle", "moderation", "omni-moderation",
            "babbage", "davinci", "ada", "curie")):
        return False
    return (
        name.startswith("gpt-")
        or name.startswith("gpt")
        or name.startswith("chatgpt-")
        or name.startswith("o1")
        or name.startswith("o3")
        or name.startswith("o4")
    )


def _fetch_live_models(provider: str, api_key: str) -> list[dict]:
    """Fetch the provider's live model list via the lazy SDK (no LM dep at module load; trivially
    mockable, like ``_probe_provider``). Filters to the chat-capable ids the council can grade
    through — OpenAI keeps ``gpt-*`` / ``o1*``/``o3*``/``o4*`` / ``chatgpt-*`` and DROPS embeddings /
    whisper / tts / dall-e / moderation / ``text-*``; Anthropic keeps ``claude-*``. Each entry is
    capability-annotated + tagged ``source:"live"``. RAISES on any SDK/network/auth error — the
    caller traps it per-provider so the catalog endpoint NEVER 500s."""
    provider = (provider or "").strip().lower()

    def _ids(listed) -> list[str]:
        rows = getattr(listed, "data", listed)
        out_ids: list[str] = []
        for m in rows:
            mid = getattr(m, "id", None)
            if mid is None and isinstance(m, dict):
                mid = m.get("id")
            if mid:
                out_ids.append(str(mid))
        return out_ids

    if provider == "openai":
        import openai  # type: ignore

        listed = openai.OpenAI(api_key=api_key).models.list()
        return [
            {"model": mid, **capabilities_for("openai", mid), "source": "live"}
            for mid in _ids(listed) if _is_openai_chat_model(mid)
        ]
    if provider == "anthropic":
        import anthropic  # type: ignore

        listed = anthropic.Anthropic(api_key=api_key).models.list()
        return [
            {"model": mid, **capabilities_for("anthropic", mid), "source": "live"}
            for mid in _ids(listed) if mid.lower().startswith("claude-")
        ]
    return []


def _model_key_var(model_id: str) -> str:
    """The per-model namespaced WRITE-ONLY env var carrying the secret on ``.provider_env`` (e.g.
    ``LITHRIM_MODEL__gpt4o_prod__KEY``). Sanitized so an arbitrary id can't inject an env-file line."""
    safe = re.sub(r"[^A-Za-z0-9]", "_", (model_id or "").strip())
    return f"LITHRIM_MODEL__{safe}__KEY"


def _read_models_registry() -> dict:
    """Read the gitignored ``.models_registry.json`` pool sidecar (a list of non-secret entries).
    Absent / malformed → an empty pool. NEVER carries a key."""
    registry_path = _models_registry_path()
    if registry_path.exists():
        try:
            stored = json.loads(registry_path.read_text())
            if isinstance(stored, dict) and isinstance(stored.get("models"), list):
                return stored
        except (json.JSONDecodeError, OSError):
            pass
    return {"models": []}


def _write_models_registry(reg: dict) -> None:
    _write_sidecar(_models_registry_path(), json.dumps(reg, indent=2) + "\n")


def _persist_model_key(model_id: str, api_key: str) -> None:
    """WRITE-ONLY persist the model's key under its namespaced var on ``.provider_env`` (REUSING
    Build A's secret hygiene — never SQLite/manifest/git/the response/logs/the registry sidecar)."""
    merged = _parse_env_file(_provider_env_path())
    merged[_model_key_var(model_id)] = api_key
    _write_sidecar(_provider_env_path(), "".join(f"{k}={v}\n" for k, v in merged.items()))


def _drop_model_key(model_id: str) -> None:
    """Remove a model's namespaced key var from ``.provider_env`` (the DELETE path)."""
    merged = _parse_env_file(_provider_env_path())
    merged.pop(_model_key_var(model_id), None)
    _write_sidecar(_provider_env_path(), "".join(f"{k}={v}\n" for k, v in merged.items()))


def _read_model_key(model_id: str) -> str | None:
    """Read a model's persisted key back from ``.provider_env`` (the BIND path needs it to wire the
    role's env). Stays on-disk: the key is never returned to a caller or logged."""
    return _parse_env_file(_provider_env_path()).get(_model_key_var(model_id))


class ModelRegisterRequest(BaseModel):
    # MODEL-REGISTRY-1a: register a configured model into the pool. ``model`` is the model id (OpenAI/
    # Anthropic) or the DEPLOYMENT name (Azure). The key is read-only test-probed (REUSING Build A's
    # ``_probe_provider``), then written ONLY write-only to ``.provider_env`` — never the response.
    # PROVIDER-CENTER-A: the provider set broadens to gemini/bedrock/openai_compatible (the litellm
    # path speaks them) — register a model on ANY of these, then bind it per-role.
    id: str
    provider: Literal["openai", "azure", "anthropic", "gemini", "bedrock", "openai_compatible", "composo"]
    model: str
    endpoint: str | None = None  # api_base — required for azure / openai_compatible
    api_key: str


class ModelBindRequest(BaseModel):
    # MODEL-REGISTRY-1a: bind a pool entry to a judge role. R2a: widened from the trio Literal to
    # ANY validated judge role id (authored roles bind too); the role REFERENCES the entry instead
    # of re-typing provider/model/key.
    role: str = Field(pattern=_ROLE_ID_PATTERN)


def _model_entry_public(entry: dict) -> dict:
    """The non-secret public projection of a pool entry — NEVER a key (defensive: a key field never
    lands in the registry, but this projection is the single response shape the API returns)."""
    return {
        "id": entry["id"],
        "provider": entry["provider"],
        "model": entry.get("model"),
        "endpoint": entry.get("endpoint"),
        "capabilities": entry.get("capabilities", {}),
        "last_tested": entry.get("last_tested"),
        "bound_roles": entry.get("bound_roles", []),
    }


def _live_provider_catalog(provider: str, presets: list[dict]) -> tuple[list[dict], dict]:
    """MODEL-REGISTRY-1b: merge a provider's presets with its LIVE ``/models`` fetch. Reads the
    already-configured key SERVER-SIDE from ``.provider_env`` (Build A's ``OPENAI_API_KEY`` /
    ``ANTHROPIC_API_KEY``) — NEVER a query param. Graceful-absent is the contract: no key OR any
    fetch error → presets-only (each ``source:"preset"``) + a per-provider status note; never 500,
    never the key in the note. On success: preset ⊕ live, deduped by ``model`` (preset wins the
    capability row), each tagged ``source``. Returns ``(rows, status)``."""
    env = _parse_env_file(_provider_env_path())
    key_var = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}.get(provider)
    api_key = (env.get(key_var) if key_var else None) or None

    preset_rows = [{**dict(m), "source": "preset"} for m in presets]
    if not api_key:
        return preset_rows, {"ok": False, "fetched": 0, "source": "presets",
                             "note": "no configured key — presets only"}
    try:
        live_rows = _fetch_live_models(provider, api_key)
    except Exception as exc:  # noqa: BLE001 — graceful per-provider fallback, never a 500
        # only the exception TYPE, never str(exc) — an SDK can echo the key into a message
        return preset_rows, {"ok": False, "fetched": 0, "source": "presets",
                             "error": type(exc).__name__,
                             "note": "live fetch failed — presets only"}

    seen = {r["model"] for r in preset_rows}
    merged = preset_rows + [r for r in live_rows if r["model"] not in seen]
    return merged, {"ok": True, "fetched": len(live_rows), "source": "presets+live"}


@app.get("/v1/models/catalog")
def models_catalog_endpoint(live: bool = Query(False)) -> dict:
    """MODEL-REGISTRY-1a/1b: the capability-aware catalog — curated presets per provider (each with a
    ``logprobs`` flag + context/cost) plus the Azure deployment-based note. ``logprobs`` is the
    load-bearing differentiator vs a cosmetic dropdown (OpenAI yes → calibrated confidence; Claude
    no → confidence dark). A CUSTOM model not in the presets is still honestly annotated client-side
    via ``capabilities_for`` (exposed at register time).

    ``?live=true`` (1b) opts in to a LIVE ``/models`` fetch for OpenAI + Anthropic using the
    already-configured key (read SERVER-SIDE from ``.provider_env`` — never a query param, never the
    response, never logged); each provider falls back to presets-only on absent-key/error (a 200,
    never a 500). The default (``live`` absent/false) returns the EXACT 1a JSON — no ``source``/
    ``live`` keys — so the additive axis cannot perturb the 1a contract. Azure is never fetched."""
    if not live:
        return {
            "providers": {
                "openai": [dict(m) for m in _MODEL_CATALOG_PRESETS["openai"]],
                "anthropic": [dict(m) for m in _MODEL_CATALOG_PRESETS["anthropic"]],
                "azure": {"models": [], "note": _MODEL_CATALOG_AZURE_NOTE},
            }
        }
    openai_rows, openai_status = _live_provider_catalog("openai", _MODEL_CATALOG_PRESETS["openai"])
    anthropic_rows, anthropic_status = _live_provider_catalog(
        "anthropic", _MODEL_CATALOG_PRESETS["anthropic"]
    )
    return {
        "providers": {
            "openai": openai_rows,
            "anthropic": anthropic_rows,
            "azure": {"models": [], "note": _MODEL_CATALOG_AZURE_NOTE},  # never fetched
        },
        "live": {"openai": openai_status, "anthropic": anthropic_status},
    }


@app.post("/v1/models")
def models_register_endpoint(
    req: ModelRegisterRequest,
    default_actor: Actor = Depends(get_actor),
    x_actor: str | None = Header(None, alias="X-Actor"),
) -> dict:
    """MODEL-REGISTRY-1a: register a configured model into the reusable pool. A READ-ONLY probe
    (REUSING Build A's ``_probe_provider`` — the same litellm/openai path ``build_judge_lm`` grades
    through) gates the write. On a clean probe: the non-secret metadata + inferred capabilities are
    stored in ``.models_registry.json`` and the key is persisted WRITE-ONLY under a namespaced var on
    ``.provider_env`` (NEVER SQLite/manifest/git/the response/logs/the registry sidecar). On probe
    failure → 400 and NOTHING is written. The response NEVER carries the key."""
    if req.provider == "azure" and not req.endpoint:
        raise HTTPException(status_code=400, detail="provider='azure' requires `endpoint`")

    probe = _probe_provider(
        plane="grading" if req.provider != "anthropic" else "assistant",
        provider=req.provider, api_key=req.api_key, endpoint=req.endpoint, model=req.model,
    )
    if not probe.get("ok"):
        raise HTTPException(
            status_code=400,
            detail=f"model test failed ({probe.get('error', 'unknown error')})",
        )

    last_tested = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    capabilities = capabilities_for(req.provider, req.model)
    entry = {
        "id": req.id,
        "provider": req.provider,
        "model": req.model,
        "endpoint": req.endpoint,
        "capabilities": capabilities,
        "last_tested": last_tested,
        "bound_roles": [],
    }

    reg = _read_models_registry()
    reg["models"] = [m for m in reg["models"] if m.get("id") != req.id] + [entry]
    _write_models_registry(reg)  # non-secret only — no key field exists on ``entry``
    _persist_model_key(req.id, req.api_key)  # the key, write-only on .provider_env

    actor = _resolve_actor(x_actor, default_actor)
    ws = workspace.get_active_workspace()
    AuditLog(db_path=ws.config_db).record(
        AuditRecord(
            actor=actor,
            action="model_register",
            target=Target(type="model", id=req.id),
            why={"rationale": f"registered + tested the {req.provider} model {req.model!r}"},
            before=None,
            # NEVER the key — only the non-secret selectors + capabilities
            after={"id": req.id, "provider": req.provider, "model": req.model,
                   "capabilities": capabilities, "last_tested": last_tested},
        )
    )
    return _model_entry_public(entry)


@app.get("/v1/models")
def models_list_endpoint() -> dict:
    """MODEL-REGISTRY-1a: the configured-model pool — non-secret metadata + capabilities only,
    NEVER a key (the key lives write-only on ``.provider_env``)."""
    reg = _read_models_registry()
    return {"models": [_model_entry_public(m) for m in reg["models"]]}


@app.delete("/v1/models/{model_id}")
def models_delete_endpoint(
    model_id: str,
    default_actor: Actor = Depends(get_actor),
    x_actor: str | None = Header(None, alias="X-Actor"),
) -> dict:
    """MODEL-REGISTRY-1a: drop a pool entry AND its write-only key from ``.provider_env``."""
    reg = _read_models_registry()
    if not any(m.get("id") == model_id for m in reg["models"]):
        raise HTTPException(status_code=404, detail=f"model {model_id!r} not in the pool")
    reg["models"] = [m for m in reg["models"] if m.get("id") != model_id]
    _write_models_registry(reg)
    _drop_model_key(model_id)

    actor = _resolve_actor(x_actor, default_actor)
    ws = workspace.get_active_workspace()
    AuditLog(db_path=ws.config_db).record(
        AuditRecord(
            actor=actor,
            action="model_delete",
            target=Target(type="model", id=model_id),
            why={"rationale": f"removed model {model_id!r} from the pool"},
            before={"id": model_id}, after=None,
        )
    )
    return {"ok": True, "id": model_id, "deleted": True}


@app.post("/v1/models/{model_id}/bind")
def models_bind_endpoint(
    model_id: str,
    req: ModelBindRequest,
    default_actor: Actor = Depends(get_actor),
    x_actor: str | None = Header(None, alias="X-Actor"),
) -> dict:
    """MODEL-REGISTRY-1a / PROVIDER-CENTER-A: bind a pool entry to one of the 3 fixed roles. Maps the
    entry's {provider, model, endpoint, key} to the role's env vars via the SAME mechanism as Build A's
    ``_provider_env_vars`` + ``_persist_and_reload_provider`` — so ``build_judge_lm`` routes that role
    to the chosen model with NO restart. CROSS-PROVIDER-PER-ROLE (PROVIDER-CENTER-A, S-BS-MR1a-
    CROSSPROVIDER closed): ``build_judge_lm`` now reads a PER-ROLE provider override
    (``LITHRIM_LLM_PROVIDER_<ROLE>`` + the per-role model/key/api_base), so binding role A→openai and
    role B→gemini and role C→anthropic SIMULTANEOUSLY is supported — a genuinely mixed council. When no
    per-role provider is bound, the global ``LITHRIM_LLM_PROVIDER`` path is byte-identical to before.
    (BYO-Claude's ``model``/``provider`` override still selects the claude-cli LM.)"""
    reg = _read_models_registry()
    entry = next((m for m in reg["models"] if m.get("id") == model_id), None)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"model {model_id!r} not in the pool")

    api_key = _read_model_key(model_id)
    if not api_key:
        raise HTTPException(
            status_code=409,
            detail=f"model {model_id!r} has no persisted key (re-register it)",
        )

    _assert_bindable_judge_role(req.role)  # R2a typo-guard: only a declared reviewer binds
    # Reuse the Build A env-var mapper: a ProviderConfigRequest carrying this entry's selectors,
    # role-targeted so only this judge's per-role model/deployment is set.
    cfg = ProviderConfigRequest(
        plane="grading", provider=entry["provider"], api_key=api_key,
        endpoint=entry.get("endpoint"), model=entry.get("model"), role=req.role,
    )
    try:
        env_vars = _provider_env_vars(cfg)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _persist_and_reload_provider(env_vars)  # os.environ + the council settings singleton, no restart

    bound = sorted(set(entry.get("bound_roles", [])) | {req.role})
    entry["bound_roles"] = bound
    _write_models_registry(reg)

    actor = _resolve_actor(x_actor, default_actor)
    ws = workspace.get_active_workspace()
    AuditLog(db_path=ws.config_db).record(
        AuditRecord(
            actor=actor,
            action="model_bind",
            target=Target(type="model", id=model_id),
            why={"rationale": f"bound model {model_id!r} to role {req.role}"},
            before=None,
            # NEVER the key — only the non-secret binding facts
            after={"id": model_id, "role": req.role, "provider": entry["provider"],
                   "model": entry.get("model")},
        )
    )
    return {
        "ok": True, "id": model_id, "role": req.role,
        "provider": entry["provider"], "model": entry.get("model"), "bound_roles": bound,
    }


@app.post("/v1/provider/config")
def provider_config_endpoint(
    req: ProviderConfigRequest,
    default_actor: Actor = Depends(get_actor),
    x_actor: str | None = Header(None, alias="X-Actor"),
) -> dict:
    """CE-PROVIDER-BACKEND (Build A, SPEC §3): configure the user's LLM provider key IN-APP. Mirrors
    ``connector_config_endpoint``: a READ-ONLY probe (a bounded 1-token completion via the same
    litellm/openai path build_judge_lm grades through; a cheap Anthropic ping for the assistant
    plane) gates the write. On a clean probe the key is written ONLY to the gitignored repo-root
    ``.provider_env`` (§3.1 step 2 — NEVER SQLite/manifest/git/the response/logs), ``os.environ`` is
    set (subprocess grades inherit it) AND the in-process council ``settings`` singleton is refreshed
    in place (build_judge_lm reads the new key with NO restart). On probe failure the status is
    surfaced (4xx) and NOTHING is written. The change is audited with the key REDACTED."""
    try:
        env_vars = _provider_env_vars(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    probe = _probe_provider(
        plane=req.plane, provider=req.provider, api_key=req.api_key,
        endpoint=req.endpoint, model=req.model, role=req.role, api_version=req.api_version,
    )
    if not probe.get("ok"):
        # surface the failing probe; do NOT write the key (non-vacuous vs the clean path)
        raise HTTPException(
            status_code=400,
            detail=f"provider test failed ({probe.get('error', 'unknown error')})",
        )

    last_tested = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    _persist_and_reload_provider(env_vars)

    # the non-secret status sidecar (provider/model/endpoint/last_tested) — NEVER the key
    status = _read_provider_status()
    status[req.plane] = {
        "configured": True,
        "provider": req.provider,
        "model": req.model,
        "endpoint": req.endpoint,
        "role": req.role,
        "last_tested": last_tested,
    }
    _write_sidecar(_provider_status_path(), json.dumps(status, indent=2) + "\n")

    actor = _resolve_actor(x_actor, default_actor)
    ws = workspace.get_active_workspace()
    AuditLog(db_path=ws.config_db).record(
        AuditRecord(
            actor=actor,
            action="provider_config",
            target=Target(type="provider", id=f"{req.plane}:{req.provider}"),
            why={"rationale": f"configured + tested the {req.provider} {req.plane} provider"},
            before=None,
            # NEVER the key — only the non-secret selectors (mirrors connector_config)
            after={"plane": req.plane, "provider": req.provider, "model": req.model,
                   "role": req.role, "last_tested": last_tested},
        )
    )
    return {
        "ok": True,
        "plane": req.plane,
        "provider": req.provider,
        "last_tested": last_tested,
    }


@app.get("/v1/provider/status")
def provider_status_endpoint() -> dict:
    """CE-PROVIDER-BACKEND (Build A, SPEC §3.2): which planes are configured + provider/model/
    last_tested — so the UI shows connected/needs-setup. NEVER the key."""
    return {"planes": _read_provider_status()}


# CONNECT-AI-CONSOLIDATE-1 ──────────────────────────────────────────────────────────────────────
# The 2-section Connect AI panel: Section 1 connects a provider with JUST a key (above); Section 2
# binds a {provider, model} to ONE consumer REUSING the provider's already-stored key — keys are
# entered ONCE. The four consumers are the 3 judges (the council) + a now-COMPULSORY cross-provider
# chat_assistant (CONV-RUNTIME-1 made the chat runtime provider-agnostic). The bind REUSES the
# stored key (read from .provider_env via _PROVIDER_SECRET_VAR[provider]) — the request body carries
# NO key, the response carries NO key. The judge bind reuses Build A's per-role LITHRIM_LLM_*_<ROLE>
# writer; the chat bind writes the CONV-RUNTIME-1 LITHRIM_CHAT_* contract loop.py consumes.
_ROLE_BIND_JUDGE_ENV = {  # role → the per-role JUDGE env (reuses _PROVIDER_ROLE_BINDING above)
    "risk_judge": "RISK", "policy_judge": "POLICY", "faithfulness_judge": "FAITHFULNESS",
}
_ROLE_BIND_CHAT = "chat_assistant"
_ROLE_BIND_CONSUMERS = (*_ROLE_BIND_JUDGE_ENV.keys(), _ROLE_BIND_CHAT)


class RoleBindRequest(BaseModel):
    # CONNECT-AI-CONSOLIDATE-1: bind a {provider, model} to ONE consumer. NO api_key — the key is
    # REUSED from the provider's already-stored secret on .provider_env (keys entered once).
    # R2a: `role` widened from the trio Literal to ANY validated judge role id (authored roles
    # bind too); the pattern doubles as the env-suffix injection guard. chat_assistant matches.
    role: str = Field(pattern=_ROLE_ID_PATTERN)
    provider: Literal["openai", "azure", "anthropic", "gemini", "bedrock", "openai_compatible", "composo"]
    model: str
    # NEW-G1: an OPTIONAL PER-ROLE endpoint (api_base) + api_version that OVERRIDE the provider's
    # stored global — so two judges on the SAME azure/openai_compatible provider can target DIFFERENT
    # deployments (distinct endpoints / api-versions) from the UI, without re-editing the connect env.
    # Absent → the existing fallback to the stored global (back-compat, binds unchanged). NOT secrets.
    endpoint: str | None = None
    api_version: str | None = None


def _stored_provider_key(provider: str) -> str | None:
    """Read a provider's already-stored GLOBAL key back from .provider_env (the bind reuses it).
    None ⇒ the provider is not connected. The key stays on-disk — never returned to a caller."""
    var = _PROVIDER_SECRET_VAR.get(provider)
    if not var:
        return None
    return _parse_env_file(_provider_env_path()).get(var) or None


def _stored_provider_endpoint(provider: str) -> str | None:
    """Read a provider's already-stored endpoint (azure / openai_compatible api_base) for reuse."""
    var = _PROVIDER_ENDPOINT_VAR.get(provider)
    if not var:
        return None
    return _parse_env_file(_provider_env_path()).get(var) or None


def _connected_providers() -> list[str]:
    """The providers with a stored key on .provider_env (Section 1's connected list). NO key."""
    env = _parse_env_file(_provider_env_path())
    return [p for p, var in _PROVIDER_SECRET_VAR.items() if env.get(var)]


def _read_role_bindings() -> dict:
    """The non-secret per-consumer readout — which {provider, model} each of the 4 roles is bound to,
    from the ``role_bindings`` config DB (ROLE-BINDINGS-DB; was ``.provider_env``). An unbound role is
    None. NEVER carries a key (the key lives write-only on ``.provider_env``)."""
    from lithrim_bench.harness import role_bindings as _rb

    stored = _rb.load_bindings(db_path=_role_bindings_db_path())
    roles: dict[str, dict | None] = {}
    # R2a: the trio always lists (the fixed rows) ∪ every stored role (authored roles appear
    # once bound). Judges live in the config DB.
    for role in dict.fromkeys([*_ROLE_BIND_JUDGE_ENV, *stored]):
        b = stored.get(role)
        roles[role] = (
            {"provider": b["provider"], "model": b.get("model")} if b and b.get("provider") else None
        )
    # the chat_assistant binding stays file-based (loop.py reads .provider_env directly, DB-free)
    env = _parse_env_file(_provider_env_path())
    chat_prov = env.get("LITHRIM_CHAT_PROVIDER")
    roles[_ROLE_BIND_CHAT] = (
        {"provider": chat_prov, "model": env.get("LITHRIM_CHAT_MODEL")} if chat_prov else None
    )
    return roles


@app.post("/v1/roles/bind")
def roles_bind_endpoint(
    req: RoleBindRequest,
    default_actor: Actor = Depends(get_actor),
    x_actor: str | None = Header(None, alias="X-Actor"),
) -> dict:
    """CONNECT-AI-CONSOLIDATE-1: assign a {provider, model} to ONE consumer (a judge or the
    compulsory chat_assistant), REUSING the provider's already-stored key — the request body carries
    NO key, and the key is read SERVER-SIDE from .provider_env (keys entered once). Re-probes with
    the stored key + chosen model BEFORE writing; a JUDGE bind writes the per-role
    LITHRIM_LLM_*_<ROLE> (Build A's writer); a chat_assistant bind writes the CONV-RUNTIME-1
    LITHRIM_CHAT_* contract (anthropic ALSO writes ANTHROPIC_API_KEY for the SDK path). 422 if the
    provider has no stored key / unknown role / azure|openai_compatible without a stored endpoint / a
    failing probe. The response is non-secret ({ok, role, provider, model}) — NO key."""
    api_key = _stored_provider_key(req.provider)
    if not api_key:
        raise HTTPException(
            status_code=422,
            detail=f"provider {req.provider!r} is not connected (connect it in Providers first)",
        )
    # NEW-G1: a PER-ROLE endpoint on the request wins over the provider's stored global (so two
    # judges on the same provider can hit different deployments); absent → the stored global.
    endpoint = (req.endpoint or "").strip() or _stored_provider_endpoint(req.provider)
    if req.provider in ("azure", "openai_compatible") and not endpoint:
        raise HTTPException(
            status_code=422,
            detail=f"provider {req.provider!r} has no stored endpoint (re-connect it with an endpoint)",
        )
    # CONNECT-AI-AZURE-1 + NEW-G1: a PER-ROLE api_version on the request wins; else REUSE the stored
    # Azure api_version (no re-entry); default to the council default. None for non-azure.
    api_version = (req.api_version or "").strip() or _stored_provider_api_version(req.provider) or (
        _settings_azure_api_version() if req.provider == "azure" else None
    )

    # re-probe the chosen model with the REUSED stored key BEFORE writing (mirrors Build A)
    probe = _probe_provider(
        plane="assistant" if req.provider == "anthropic" else "grading",
        provider=req.provider, api_key=api_key, endpoint=endpoint, model=req.model,
        api_version=api_version,
    )
    if not probe.get("ok"):
        raise HTTPException(
            status_code=422,
            detail=f"provider test failed ({probe.get('error', 'unknown error')})",
        )

    if req.role != _ROLE_BIND_CHAT:
        # a JUDGE (any role that isn't the chat consumer — R2a: authored roles bind as judges;
        # the old trio-membership dispatch silently routed an authored role into the CHAT branch
        # and clobbered LITHRIM_CHAT_*) → the per-role binding via Build A's mapper (the REUSED
        # key fills the per-role var); the REUSED stored api_version threads for an azure judge.
        _assert_bindable_judge_role(req.role)  # the typo-guard: only a declared reviewer binds
        cfg = ProviderConfigRequest(
            plane="grading", provider=req.provider, api_key=api_key,
            endpoint=endpoint, model=req.model, role=req.role, api_version=api_version,
        )
        env_vars = _provider_env_vars(cfg)
    else:
        # chat_assistant → the CONV-RUNTIME-1 LITHRIM_CHAT_* contract (cross-provider chat)
        env_vars = {
            "LITHRIM_CHAT_PROVIDER": req.provider,
            "LITHRIM_CHAT_MODEL": req.model,
            "LITHRIM_CHAT_API_KEY": api_key,  # the REUSED stored key (write-only)
        }
        if endpoint:
            env_vars["LITHRIM_CHAT_API_BASE"] = endpoint
        if req.provider == "azure" and api_version:  # the REUSED stored version (no re-entry)
            env_vars["LITHRIM_CHAT_API_VERSION"] = api_version
        if req.provider == "anthropic":
            env_vars["ANTHROPIC_API_KEY"] = api_key  # the SDK path reads this, exactly as the assistant plane

    _persist_and_reload_provider(env_vars)

    actor = _resolve_actor(x_actor, default_actor)
    ws = workspace.get_active_workspace()
    AuditLog(db_path=ws.config_db).record(
        AuditRecord(
            actor=actor,
            action="role_bind",
            target=Target(type="role", id=req.role),
            why={"rationale": f"bound {req.role} to {req.provider} {req.model!r} (reused stored key)"},
            before=None,
            # NEVER the key — only the non-secret binding facts
            after={"role": req.role, "provider": req.provider, "model": req.model},
        )
    )
    return {"ok": True, "role": req.role, "provider": req.provider, "model": req.model}


def _chat_ready() -> bool:
    """FIRST-CONTACT-1: can the composer's next message actually be answered? Mirrors the chat
    runtime's own dispatch — a litellm chat provider is configured, OR the SDK path is importable
    (host installs with the [agent] extra + the claude CLI). The shell's first-paint "Connect AI"
    signpost renders off this, so it is false ONLY when a send would genuinely fail."""
    from agent.loop import _chat_provider_config

    if _chat_provider_config() is not None:
        return True
    try:
        import claude_agent_sdk  # noqa: F401

        return True
    except ImportError:
        return False


@app.get("/v1/roles/bindings")
def roles_bindings_endpoint() -> dict:
    """CONNECT-AI-CONSOLIDATE-1: the non-secret per-consumer readout the Assign-models section
    renders — which {provider, model} each of the 4 roles is bound to (None when unbound) + the list
    of CONNECTED providers (those with a stored key) for the Providers list. NEVER a key.
    FIRST-CONTACT-1 adds `chat_ready` (additive) — the shell's connect-the-assistant signpost."""
    return {
        "roles": _read_role_bindings(),
        "connected_providers": _connected_providers(),
        "chat_ready": _chat_ready(),
    }


def _ingest_storyworld(ws, req, *, actor: Actor) -> dict:
    """NARR-6c: the real-field batch ingest, DETERMINISTIC direct-write. Load ``base_url`` + key
    (env override first, then ``.connector_env``), paginate ``/api/admin/sessions``, fetch each
    detail, and per session run ``_prepare_storyworld_session`` (one record per ``llm_calls`` entry,
    §8.1 PII drop+redact — CONN-2) → map each prepped record through the FROZEN
    ``_to_envelope`` and write DIRECTLY. NO DSPy generation / NO LM / NO ``:3031`` — the prep is
    already correct §4.1-shaped (A-LIVE verified), so re-deriving a JUTE transform was redundant
    and (proven live) did not converge. Union all sessions' enveloped cases into ``ws.out_dir/
    ingested_cases.jsonl`` (each enriched with ``session_id``); the D1 bridge grades these.
    Per-session errors (401/404/timeout) are trapped structurally — nothing written. One batch-
    summary AuditRecord (§8.4); the key is never returned. ``_ingest_cases`` (the CHAT ingest path
    for arbitrary JSON) is unchanged — only this connector endpoint went direct-write.

    CONN-1: extracted to a per-connector adapter (keyed by ``connector_id`` in
    :data:`_CONNECTOR_INGEST_ADAPTERS`); the bespoke StoryWorld pull below is untouched.
    """
    env = _load_connector_env(ws)
    api_key = os.environ.get(_STORYWORLD_KEY_VAR) or env.get(_STORYWORLD_KEY_VAR)
    base_url = (
        os.environ.get("STORYWORLD_BASE_URL")
        or _read_connector_sidecar(ws).get("base_url")
        or ""
    )
    if not api_key or not base_url:
        raise HTTPException(
            status_code=400,
            detail="StoryWorld connector not configured (POST /v1/connector/config first)",
        )

    # NARR-6c/CONN-2: _prepare_storyworld_session produces correct §4.1-shaped per-llm_call records
    # DETERMINISTICALLY (response_preview as the artifact, finish_reason carried, §8.1 PII dropped).
    # The old per-session ctx.ingest_cases() redundantly re-derived a JUTE transform via DSPy, which
    # needs an LM and (proven live) does NOT converge — every session trapped, 0 cases. So map each
    # prepped record through the FROZEN _to_envelope and write DIRECTLY: $0, deterministic, instant,
    # no LM / no :3031 / no generation. _ingest_cases + the chat path stay byte-identical (the
    # connector no longer drives the extractor; the chat ingest_cases path still does, for arbitrary
    # JSON). No tool context is needed here anymore.
    from lithrim_bench.verification import StoryWorldAdminClient
    from lithrim_bench.verification.jute_extractor import _to_envelope

    client = StoryWorldAdminClient(base_url, api_key=api_key)

    union: dict[str, dict] = {}
    sessions_seen = 0
    errors_trapped = 0
    try:
        listing = client.list_sessions(limit=req.limit, offset=req.offset)
        items = listing.get("items", []) if isinstance(listing, dict) else []
    except Exception as exc:  # noqa: BLE001 — a list failure is a trapped batch error, not a crash
        raise HTTPException(status_code=502, detail=f"StoryWorld list failed: {exc}") from exc

    for item in items:
        session_id = item.get("id") if isinstance(item, dict) else item
        try:
            detail = client.get_session(session_id)
            records = _prepare_storyworld_session(detail)
            if not records:
                continue
            sessions_seen += 1
            for r in records:
                case = _to_envelope(r)
                cid = case.get("case_id")
                if not cid:
                    continue
                # enrich with session_id (the frozen _to_envelope drops it) for the union write
                union[cid] = {**case, "session_id": session_id}
        except Exception:  # noqa: BLE001 — 401/404/timeout: trap structurally, never fabricate
            errors_trapped += 1
            continue

    # union write (the D1 bridge grades these); enriches each envelope with session_id.
    corpus = ws.out_dir / "ingested_cases.jsonl"
    ws.out_dir.mkdir(parents=True, exist_ok=True)
    existing: dict[str, dict] = {}
    if corpus.exists():
        for line in corpus.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("case_id"):
                existing[row["case_id"]] = row
    existing.update(union)
    if union:  # only rewrite when this batch added cases (a clean mis-join leaves the corpus alone)
        corpus.write_text(
            "\n".join(json.dumps(r, sort_keys=True) for r in existing.values())
            + ("\n" if existing else "")
        )
        _ssot_upsert_cases(ws, list(union.values()))  # PERSIST-3a: the SSOT cases table

    # ONE batch-summary AuditRecord (§8.4) — the ONLY audit on this path: NARR-6c writes the prepped
    # records directly via _to_envelope (deterministic direct-write, no LLM / no :3031 / no per-session
    # ingest audits — the generation that fired those per-session audits is gone).
    AuditLog(db_path=ws.config_db).record(
        AuditRecord(
            actor=actor,
            action="ingest_batch",
            target=Target(type="corpus", id=req.agent),
            why={
                "rationale": (
                    f"StoryWorld batch ingest: {len(union)} cases from {sessions_seen} "
                    f"session(s) ({errors_trapped} trapped)"
                )
            },
            before=None,
            after={
                "count": len(union),
                "sessions": sessions_seen,
                "errors_trapped": errors_trapped,
                "case_ids": list(union.keys()),
            },
        )
    )
    return {
        "count": len(union),
        "sessions": sessions_seen,
        "cases": list(union.keys()),
        "errors_trapped": errors_trapped,
    }


# ── CONN-1: the registry-driven connector surface ──────────────────────────────────────────
# The connector panel reads GET /v1/connectors (the ingest-capable subset of
# plugins.tool_plugins() — declaration-driven, License-gated, secrets never returned) and ingests
# through POST /v1/connector/ingest, which dispatches by connector_id to a per-connector pull
# adapter. Adding a connector is a manifest entry (+ an adapter here, if it pulls) — never a UI
# edit. Today storyworld_admin is the only wired pull adapter; the JUTE connector is a transform
# engine (no service.ingest flag) and is intentionally excluded from the ingest picker.
_CONNECTOR_INGEST_ADAPTERS = {
    "storyworld_admin": _ingest_storyworld,
}


class ConnectorIngestRequest(BaseModel):
    connector_id: str
    limit: int = 50
    offset: int = 0
    agent: str = DEFAULT_AGENT


@app.get("/v1/connectors")
def connectors_list_endpoint() -> dict:
    """CONN-1: the ingest-capable connectors declared in the ACTIVE WORKSPACE's pack tool registry
    (``plugins.tool_plugins(pack=ws.pack)``, License-gated). Keyed to the workspace's pack — NOT the
    BFF process env — so a narrative workspace served through a differently-pinned process still
    sees its connectors. Projects ONLY display-safe fields — never a key, never a service secret.
    The shell renders this as the connector picker (no hardcoded source).
    """
    from lithrim_bench.harness import plugins

    ws = workspace.get_active_workspace()
    lic = plugins.default_license()
    out: list[dict] = []
    for p in plugins.tool_plugins(pack=getattr(ws, "pack", None)):
        if not lic.permits(p.id):
            continue
        svc = p.service or {}
        if not svc.get("ingest"):
            continue
        out.append(
            {
                "connector_id": p.id,
                "label": svc.get("label") or p.id,
                "default_base_url": svc.get("default_base_url", ""),
                "transport": p.transport,
            }
        )
    return {"connectors": out}


@app.post("/v1/connector/ingest")
def connector_ingest_endpoint(
    req: ConnectorIngestRequest,
    default_actor: Actor = Depends(get_actor),
    x_actor: str | None = Header(None, alias="X-Actor"),
) -> dict:
    """CONN-1: generic batch ingest — dispatch by ``connector_id`` to a per-connector pull
    adapter. A declaration-only connector (no wired adapter) is a clean 400; nothing written.
    """
    adapter = _CONNECTOR_INGEST_ADAPTERS.get(req.connector_id)
    if adapter is None:
        raise HTTPException(
            status_code=400,
            detail=f"connector {req.connector_id!r} has no ingest adapter",
        )
    ws = workspace.get_active_workspace()
    return adapter(ws, req, actor=_resolve_actor(x_actor, default_actor))


@app.post("/v1/connector/storyworld/ingest")
def storyworld_ingest_endpoint(
    req: StoryworldIngestRequest,
    default_actor: Actor = Depends(get_actor),
    x_actor: str | None = Header(None, alias="X-Actor"),
) -> dict:
    """NARR-6c legacy route — back-compat delegator to the storyworld_admin adapter (CONN-1)."""
    ws = workspace.get_active_workspace()
    return _ingest_storyworld(ws, req, actor=_resolve_actor(x_actor, default_actor))


@app.post("/v1/cases/ingest/preview")
def ingest_preview_endpoint(
    req: IngestPreviewRequest,
    db_path: Path = Depends(get_config_db),
    out_dir: Path | None = Depends(get_out_dir),
    workdir: Path = Depends(get_ontology_workdir),
    collections_db: Path = Depends(get_collections_db),
    default_actor: Actor = Depends(get_actor),
    x_actor: str | None = Header(None, alias="X-Actor"),
) -> dict:
    """CE-INGEST-FRONTDOOR-1: decode an uploaded JSON/JSONL/CSV blob, select/generate a JUTE
    template, apply it, and return the extracted cases + the template for the human to validate.
    Pins NOTHING and writes NO corpus — the human approves at /commit. A bad blob / non-converging
    transform is a calm 422 (the front door surfaces the reason), never a bare 500."""
    actor = _resolve_actor(x_actor, default_actor)
    agent = _resolve_chat_agent(req.agent, db_path)
    ctx = _build_tool_context(agent, db_path, out_dir, workdir, collections_db, actor, x_actor)
    try:
        return ctx.ingest_preview(
            raw=req.raw, fmt=req.fmt, filename=req.filename,
            extraction_rules=req.extraction_rules, agent=agent,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/v1/cases/ingest/commit")
def ingest_commit_endpoint(
    req: IngestCommitRequest,
    db_path: Path = Depends(get_config_db),
    out_dir: Path | None = Depends(get_out_dir),
    workdir: Path = Depends(get_ontology_workdir),
    collections_db: Path = Depends(get_collections_db),
    default_actor: Actor = Depends(get_actor),
    x_actor: str | None = Header(None, alias="X-Actor"),
) -> dict:
    """CE-INGEST-FRONTDOOR-1: pin the human-APPROVED template + upsert the corpus (no LM gen). The
    decode is deterministic, so this reproduces exactly the cases shown in /preview."""
    actor = _resolve_actor(x_actor, default_actor)
    agent = _resolve_chat_agent(req.agent, db_path)
    ctx = _build_tool_context(agent, db_path, out_dir, workdir, collections_db, actor, x_actor)
    try:
        return ctx.ingest_commit(
            approved_template=req.approved_template, raw=req.raw, fmt=req.fmt,
            filename=req.filename, extraction_rules=req.extraction_rules, agent=agent,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ── RIGOR-1 read surface: GET /v1/reliability/{agent} ─────────────────────────


def _reliability_run_record(doc: dict, golds: dict[str, set]) -> dict:
    """Normalize a persisted provenance blob into the run-record shape
    ``reliability.compute_report`` consumes: the per-judge votes (role/vote/confidence/model)
    AS RECORDED, plus the deterministic-floor outcome (covered / correct-vs-gold) derived from
    the persisted ``grounded`` block. Pure projection — the same blob the run-audit read projects.

    Floor coverage = the floor spoke on this case (it suppressed a finding OR enforced a block).
    An absent / empty ``grounded`` block is an ABSTENTION (not covered), not a fabricated pass —
    the honest "the floor could not ground this" state the selective-prediction metric reports."""
    semantic = (doc.get("stage_results") or {}).get("semantic") or {}
    cid = doc.get("case_id")
    votes = [
        {
            "judge_role": v.get("judge_role"),
            "vote": v.get("vote"),
            "confidence": v.get("confidence"),
            "model": v.get("model"),
        }
        for v in (semantic.get("judge_votes") or [])
    ]
    grounded = doc.get("grounded") or {}
    floor = None
    if grounded:
        covered = bool(grounded.get("suppressed") or grounded.get("floor_blocks"))
        if covered:
            gold_block = bool(golds.get(cid))
            floor = {
                "covered": True,
                "correct": _is_blocked_verdict(grounded.get("verdict")) == gold_block,
            }
        else:
            floor = {"covered": False, "correct": None}
    return {
        "case_id": cid,
        "verdict": doc.get("verdict"),
        "votes": votes,
        "floor": floor,
    }


@app.get("/v1/reliability/{agent}")
def get_reliability_endpoint(
    agent: str,
    limit: int = Query(500, ge=1, le=2000),
    db_path: Path = Depends(get_config_db),
    collections_db: Path = Depends(get_collections_db),
) -> dict:
    """RIGOR-1 in the product: the statistical-rigour reliability metrics — Fleiss/Cohen kappa,
    10-bin ECE + Brier, pairwise-error phi + effective independent votes, floor selective-
    prediction, and intra-judge stability — computed from THIS agent's OWN persisted runs joined
    to the ingested-corpus gold the cohort scorecard reads. Agent-scoped ($0 pure read).

    HONESTY CONTRACT (``lithrim_bench.reliability``): every metric carries its own
    ``insufficient`` flag with a plain reason — a thin/degenerate workspace (no repeats for
    intra-judge stability, no gold for calibration, n too small for chance-correction) yields a
    flagged ``null``, NEVER a fabricated number. Unknown agent → 404 (the ``_load_agent``
    convention); a known agent with no runs → all-insufficient metrics, not zeros-as-data."""
    from lithrim_bench import reliability

    _load_agent(agent, db_path)  # 404 on an unknown agent
    docs = run_coro(provenance_store_for(collections_db).list_all(limit=None))
    mine = [d for d in docs if d.get("agent_id") == agent]
    mine.sort(key=lambda d: str(d.get("timestamp") or ""))
    mine = mine[-limit:]
    golds, labeled = _corpus_golds_labeled(_read_ingested_corpus())
    records = [_reliability_run_record(d, golds) for d in mine]
    report = reliability.compute_report(runs=records, golds=golds, labeled=labeled)
    return {"agent": agent, "metrics": report, "n_runs": report["n_runs"]}


def _sweep_sample_runs(docs: list[dict], *, role: str | None = None) -> list[list[float]]:
    """The per-case ``scores_raw`` for the K-sweep — one sample list per (case, reviewer) with
    >= 1 recorded sample. Pure projection off ``stage_results.semantic.judge_votes[*].scores_raw``
    (the same blob the reliability read projects). ``role`` scopes to a single reviewer when given;
    otherwise every reviewer's own sampled runs contribute (each is its OWN self-consistency
    curve — the sweep never mixes samples across reviewers on a case). A vote with no ``scores_raw``
    (a k=1 run may omit it) is skipped — the sweep needs the raw K samples."""
    runs: list[list[float]] = []
    for doc in docs:
        semantic = (doc.get("stage_results") or {}).get("semantic") or {}
        for v in semantic.get("judge_votes") or []:
            if role is not None and v.get("judge_role") != role:
                continue
            raw = v.get("scores_raw")
            if isinstance(raw, list) and raw:
                runs.append([float(s) for s in raw if isinstance(s, (int, float))])
    return [r for r in runs if r]


@app.get("/v1/reliability/{agent}/sweep")
def get_reliability_sweep_endpoint(
    agent: str,
    k_max: int | None = Query(None, ge=1, le=64),
    role: str | None = Query(None),
    limit: int = Query(500, ge=1, le=2000),
    db_path: Path = Depends(get_config_db),
    collections_db: Path = Depends(get_collections_db),
) -> dict:
    """RIGOR-1 / Q1 (NEW-G3) in the product: the single-reviewer K-sweep self-consistency curve —
    flip-rate / majority-convergence / variance with Wilson CIs, for K = 1..``k_max``, computed
    from THIS agent's OWN persisted per-sample scores (``scores_raw``). Agent-scoped ($0 pure read),
    NO gold dependency (the sweep measures a reviewer against ITSELF, not the answer key).

    HONESTY CONTRACT (``lithrim_bench.reliability.sweep_series``): no sampled runs → an
    ``insufficient`` sweep with an empty series and a plain reason, NEVER a fabricated 0.0 curve.
    Unknown agent → 404 (the ``_load_agent`` convention). ``k_max`` defaults to (and is clamped to)
    the longest sample run seen; ``role`` scopes to one reviewer."""
    from lithrim_bench import reliability

    _load_agent(agent, db_path)  # 404 on an unknown agent
    docs = run_coro(provenance_store_for(collections_db).list_all(limit=None))
    mine = [d for d in docs if d.get("agent_id") == agent]
    mine.sort(key=lambda d: str(d.get("timestamp") or ""))
    mine = mine[-limit:]
    cases = _sweep_sample_runs(mine, role=role)
    sweep = reliability.sweep_series(cases, k_max=k_max)
    return {"agent": agent, "sweep": sweep, "n_cases": len(cases)}
