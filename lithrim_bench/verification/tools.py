"""The WS-3 verification toolbox: generic backends behind one `VerificationTool`.

| tool             | access                              | determinism                              |
|------------------|-------------------------------------|------------------------------------------|
| StructuralJute   | etlp `:3031` Jute validator         | mapping selector + content-hash PIN      |
| KbRagTool        | backend KB `:8002 /v1/kb/search`    | pinned namespace + retrieval verdict     |
| RecordRagTool    | `lithrim_search_sdk` + Pinecone     | pinned corpus + retrieval manifest       |

The CLINICAL executors (the record-presence `InRowTool` + the `DosageGroundingTool`
floor + their SOAP/PMH/dose extractors) relocated OUT of the core into the active pack
(`packs/healthcare/floors.py`, PACK-3); the generic helpers `_dig`/`_norm` they depend on
stay here and the pack imports them. Every tool returns a tri-state `conforms` (see
`spec.py`). The flag-clearing
decision lives in `router.compose_verdict`, not in the tools — a tool only
answers "does this locus conform to the pinned reference?".

WIRE CONTRACT NOTE (StructuralJute): the committed
`lithrim_bench/backends/etlp_structural.py` is STALE — live-probed `:3031`
(2026-05-31) requires `POST /parse-hl7 {"message": <raw>}` (NOT `{"hl7": ...}`)
and `POST /mappings/{id}/apply {"data": {"resource": <inner>}}` (NOT
`{"resource": ...}`), and mapping IDs RESEED (the paper's id 93 is already
gone; current ADT-A04 = id 26). This tool uses the correct contract and pins by
selector(title)+content-hash so a reseed surfaces as DRIFT instead of silently
scoring against the wrong mapping.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from abc import ABC, abstractmethod
from typing import Any

from .spec import (
    TOOL_KB_RAG,
    Claim,
    VerificationResult,
    VerificationSpec,
)


class VerificationTool(ABC):
    name: str = ""

    def handles(self, spec: VerificationSpec) -> bool:
        return spec.tool == self.name

    @abstractmethod
    def verify(self, claim: Claim, spec: VerificationSpec) -> VerificationResult: ...


# --------------------------------------------------------------------------- #
# shared text helpers (generic; the relocated clinical executors import these)
# --------------------------------------------------------------------------- #
def _norm(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower())


def _dig(source: dict, dotted_path: str) -> list:
    """Navigate a dotted path into the case row; return a list ([] if absent/non-list)."""
    cur: Any = source
    for part in dotted_path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return []
    return cur if isinstance(cur, list) else ([] if cur is None else [cur])


# --------------------------------------------------------------------------- #
# StructuralJuteTool — etlp :3031, selector+content-hash pinned (drift-refuse)
# --------------------------------------------------------------------------- #
class StructuralJuteTool(VerificationTool):
    """HL7/FHIR conformance via the etlp-mapper Jute validator at `:3031`.

    `http_client` is injectable for tests (an httpx.Client-like object with
    `.get(url)` / `.post(url, json=...)` returning objects with `.json()` and
    `.raise_for_status()`). When omitted, an `httpx.Client` is created lazily.
    """

    name = "structural_jute"

    def __init__(self, *, http_client: Any | None = None, timeout: float = 30.0) -> None:
        self._client = http_client
        self._timeout = timeout

    def verify(self, claim: Claim, spec: VerificationSpec) -> VerificationResult:
        ref = spec.reference
        base = str(ref["service"]).rstrip("/")
        selector = ref["mapping_selector"]
        client, owns = self._acquire(client_base=base)
        try:
            mappings = self._get(client, base, "/mappings")
            mapping = self._resolve(mappings, selector)
            manifest: dict = {
                "tool": self.name,
                "deterministic": True,
                "service": base,
                "selector": selector,
                "spec_version": spec.version,
                "artifact_kind": ref["artifact_kind"],
            }
            if mapping is None:
                manifest["drift"] = "mapping_not_found"
                return VerificationResult(
                    conforms=None,
                    evidence={"error": "mapping not found", "selector": selector},
                    manifest=manifest,
                )

            resolved_id = mapping.get("id")
            observed = self._content_hash(mapping)
            pinned = ref.get("pinned_content_sha256")
            drift = bool(pinned) and observed != pinned
            manifest.update(
                resolved_id=resolved_id, observed_sha256=observed, pinned_sha256=pinned, drift=drift
            )
            if drift:
                # determinism guardrail: a reseeded/edited mapping no longer matches the
                # SME's pin. REFUSE (conforms=None) rather than score against drift.
                return VerificationResult(
                    conforms=None,
                    evidence={
                        "error": "mapping content drifted from pinned hash; refusing to score",
                        "observed_sha256": observed,
                        "pinned_sha256": pinned,
                    },
                    manifest=manifest,
                )

            resource = self._to_resource(client, base, ref["artifact_kind"], claim.subject)
            applied = self._post(
                client, base, f"/mappings/{resolved_id}/apply", {"data": {"resource": resource}}
            )
            checks = self._find_checks(applied)
            failed = [c for c in checks if str(c.get("status", "")).lower() == "fail"]
            conforms = len(failed) == 0
            manifest.update(checks_total=len(checks), failed_count=len(failed))
            evidence = {
                "artifact_kind": ref["artifact_kind"],
                "checks_total": len(checks),
                "failed": [
                    {"name": c.get("name"), "field": c.get("field"), "message": c.get("message")}
                    for c in failed
                ],
            }
            return VerificationResult(conforms=conforms, evidence=evidence, manifest=manifest)
        finally:
            if owns:
                client.close()

    # --- HTTP plumbing (correct live :3031 contract) --- #
    def _acquire(self, *, client_base: str) -> tuple[Any, bool]:
        if self._client is not None:
            return self._client, False
        import httpx

        return httpx.Client(timeout=self._timeout), True

    def _get(self, client: Any, base: str, path: str) -> Any:
        resp = client.get(base + path)
        resp.raise_for_status()
        return resp.json()

    def _post(self, client: Any, base: str, path: str, body: dict) -> Any:
        resp = client.post(base + path, json=body)
        resp.raise_for_status()
        return resp.json()

    def _to_resource(self, client: Any, base: str, artifact_kind: str, subject: Any) -> Any:
        if str(artifact_kind).startswith("hl7"):
            parsed = self._post(client, base, "/parse-hl7", {"message": subject})
            return parsed.get("parsed", parsed) if isinstance(parsed, dict) else parsed
        # FHIR: subject is already a resource dict (or its JSON string)
        if isinstance(subject, str):
            try:
                return json.loads(subject)
            except (TypeError, ValueError):
                return subject
        return subject

    @staticmethod
    def _resolve(mappings: Any, selector: dict) -> dict | None:
        rows = mappings if isinstance(mappings, list) else (mappings or {}).get("mappings", [])
        by, val = selector["by"], selector["value"]
        for m in rows:
            if not isinstance(m, dict):
                continue
            if by == "id" and m.get("id") == val:
                return m
            if by == "title" and (m.get("title") or m.get("name")) == val:
                return m
        return None

    @staticmethod
    def _content_hash(mapping: dict) -> str:
        content = mapping.get("content", mapping)
        blob = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    @staticmethod
    def _find_checks(applied: Any) -> list[dict]:
        """Recurse to the first list whose items are dicts carrying a 'status' key.

        Apply responses nest the checks under result.checks OR result.<root>.checks
        depending on the mapping (per the live :3031 contract).
        """
        found: list[dict] = []

        def walk(node: Any) -> None:
            nonlocal found
            if found:
                return
            if isinstance(node, list):
                if node and all(isinstance(x, dict) and "status" in x for x in node):
                    found = node
                    return
                for x in node:
                    walk(x)
            elif isinstance(node, dict):
                for v in node.values():
                    walk(v)

        walk(applied)
        return found


# --------------------------------------------------------------------------- #
# KbRagTool — claim grounding via the live backend KB (:8002 /v1/kb/search)
# --------------------------------------------------------------------------- #
class KbRagTool(VerificationTool):
    """Ground a council claim against the backend knowledge base — the S-BS-7
    presence-check generalized from the transcript to the KB corpus.

    The heavy retrieval (Pinecone hybrid dense+SPLADE over ``hipaa-compliancev2``)
    STAYS in lithrim-backend, already served at ``GET :8002/v1/kb/{namespace}/search``.
    This tool is bench-side wiring only: a lazy ``httpx`` GET to that endpoint plus a
    deterministic verdict over the returned matches. No vector store, no ONNX, no
    Pinecone client is pulled into the bench (that is the deferred S-BS-5).

    The wire contract (live-confirmed 2026-06-02, ``lithrim-backend/app/routes/kb.py``)::

        GET :8002/v1/kb/{namespace}/search?q=<query>&top_k=<n>
        -> {"namespace", "query", "top_k", "total_hits",
            "results": [{"id", "score", "text", "metadata"}], "duration_ms"}

    Auth: API-key callers pass ``X-API-Key`` + a ``kb:read:<namespace>`` scope; the
    header is read from ``reference.api_key`` or env (``LITHRIM_KB_API_KEY`` /
    ``LITHRIM_API_KEY``) and omitted when neither is set (open/dev backends).

    Tri-state (the false-negative guardrail in :mod:`spec`):
      * conforms=True  — a match clears ``min_score`` AND (when a ``match`` predicate
        is pinned) the claim text is corroborated by the matched chunk. The flag may
        be cleared: the KB GROUNDS the claim the council called a violation.
      * conforms=False — only when the SME pins ``expect="absent"`` (a disprove-by-
        retrieval contract) and the KB DOES return a clearing hit. Default contracts
        never return False (KB silence is not proof of a violation).
      * conforms=None  — no hit / below threshold / predicate unmet / endpoint error.
        Inconclusive: never clears a flag by silence (CLAUDE.md core invariant).

    reference = {"namespace": "hipaa",                       # required (catalog ns)
                 "service": "http://localhost:8002",         # default :8002
                 "query_field": "detail" | "<claim attr>",   # what to retrieve on
                 "top_k": 5, "min_score": 0.0,
                 "match": "claim_in_chunk" | None,            # corroboration predicate
                 "expect": "present" | "absent",             # default "present"
                 "api_key": <opt>}
    """

    name = TOOL_KB_RAG

    _DEFAULT_SERVICE = "http://localhost:8002"

    def __init__(self, *, http_client: Any | None = None, timeout: float = 30.0) -> None:
        self._client = http_client
        self._timeout = timeout

    def verify(self, claim: Claim, spec: VerificationSpec) -> VerificationResult:
        ref = spec.reference
        namespace = ref["namespace"]
        base = str(ref.get("service") or self._DEFAULT_SERVICE).rstrip("/")
        query = self._query(claim, ref)
        top_k = int(ref.get("top_k", 5))
        min_score = float(ref.get("min_score", 0.0))
        expect = str(ref.get("expect", "present"))
        match = ref.get("match")

        manifest = {
            "tool": self.name,
            "deterministic": False,  # composes over a live retrieval index
            "spec_version": spec.version,
            "locus": spec.locus,
            "service": base,
            "namespace": namespace,
            "top_k": top_k,
            "min_score": min_score,
            "expect": expect,
            "match": match,
        }

        try:
            results = self._search(base, namespace, query, top_k, ref)
        except Exception as exc:  # noqa: BLE001 - network/transport/HTTP -> inconclusive, never clears
            manifest["error"] = f"{type(exc).__name__}: {exc}"
            return VerificationResult(
                conforms=None,
                evidence={"query": query, "error": manifest["error"], "grounding": "kb_rag_v0"},
                manifest=manifest,
            )

        scored = [r for r in results if float(r.get("score", 0.0)) >= min_score]
        corroborated = [r for r in scored if self._corroborates(match, query, r)]
        top_score = max((float(r.get("score", 0.0)) for r in results), default=0.0)
        grounded = bool(corroborated)

        evidence = {
            "query": query,
            "retrieved": len(results),
            "scored": len(scored),
            "corroborated_ids": [r.get("id") for r in corroborated],
            "top_score": top_score,
            "grounding": "kb_rag_v0",
        }
        # expect="present" (default): a corroborated hit GROUNDS the claim -> clear (True);
        # nothing grounding -> inconclusive (None), never a silent confirm.
        # expect="absent": a corroborated hit DISPROVES an absence claim -> VIOLATION (False);
        # nothing found -> inconclusive (None).
        if expect == "absent":
            conforms: bool | None = False if grounded else None
        else:
            conforms = True if grounded else None
        return VerificationResult(conforms=conforms, evidence=evidence, manifest=manifest)

    # --- query extraction --- #
    @staticmethod
    def _query(claim: Claim, ref: dict) -> str:
        """The retrieval query: an explicit ``reference.query``, else the claim attr
        named by ``query_field`` (``subject`` by default), else the claim subject."""
        if ref.get("query"):
            return str(ref["query"])
        field_name = ref.get("query_field") or "subject"
        value = getattr(claim, field_name, None)
        if value is None and isinstance(claim.subject, dict):
            value = claim.subject.get(field_name)
        return str(value if value is not None else claim.subject)

    # --- corroboration predicate --- #
    @staticmethod
    def _corroborates(match: Any, query: str, result: dict) -> bool:
        """Does this match support the claim? ``None`` => retrieval-presence only (any
        scored hit corroborates). ``claim_in_chunk`` => the claim's content tokens
        overlap the matched chunk text (a cheap lexical grounding floor; semantic
        judge-calls-tool grounding is the deferred graduation)."""
        if not match:
            return True
        text = _norm(result.get("text") or "")
        if match == "claim_in_chunk":
            q = {t for t in _norm(query).split() if len(t) >= 4}
            return bool(q) and bool(q & set(text.split()))
        raise ValueError(f"unknown kb_rag match predicate {match!r}")

    # --- HTTP plumbing (GET :8002/v1/kb/{namespace}/search) --- #
    def _search(self, base: str, namespace: str, query: str, top_k: int, ref: dict) -> list[dict]:
        client, owns = self._acquire()
        try:
            url = f"{base}/v1/kb/{namespace}/search"
            params = {"q": query, "top_k": top_k}
            if ref.get("org_id"):
                params["org_id"] = ref["org_id"]
            headers = self._headers(ref)
            resp = client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            payload = resp.json()
            return list(payload.get("results") or []) if isinstance(payload, dict) else []
        finally:
            if owns:
                client.close()

    @staticmethod
    def _headers(ref: dict) -> dict:
        key = ref.get("api_key") or os.environ.get("LITHRIM_KB_API_KEY") or os.environ.get(
            "LITHRIM_API_KEY"
        )
        return {"X-API-Key": key} if key else {}

    def _acquire(self) -> tuple[Any, bool]:
        if self._client is not None:
            return self._client, False
        import httpx

        return httpx.Client(timeout=self._timeout), True


# --------------------------------------------------------------------------- #
# RecordRagTool — pinned-reference conformance via lithrim_search_sdk
# --------------------------------------------------------------------------- #
class RecordRagTool(VerificationTool):
    """Conformance to a PINNED external reference (policy@date / record / CRM entry)
    via the real `lithrim_search_sdk` (SearchClient + build_retrieval_manifest).

    The SDK pulls onnxruntime/pinecone/pymongo and needs live infra + ONNX models;
    imports are LAZY so importing this module never requires them. In an
    unconfigured env, `verify` raises a clear RuntimeError naming exactly what is
    missing. For offline tests use `FakeRecordRagTool`, which exercises the same
    interface + manifest contract without any heavy deps.

    Model weights: the ~1GB ONNX models are vendored (gitignored) under the spike's
    `models/` dir and used by default; override via `reference.dense_model_path` /
    `.sparse_model_path` or env (`LITHRIM_DENSE_MODEL_PATH` / `DENSE_MODEL_PATH`).
    A live `search()` ALSO needs `PINECONE_API_KEY`, `MONGO_URI`, and the
    jurisdiction index/collection env (`<J>_VDB_INDEX` / `<J>_AUGMENTED_COLLECTION`)
    + a corpus — the SDK is hardwired to a Mongo-backed hybrid index.

    reference = {"client": "lithrim_search_sdk",
                 "filters": {jurisdiction, code_year, categories, corpus_version, document_ids},
                 "top_k": 5, "min_score": 0.5, "as_of": "YYYY-MM-DD",
                 "dense_model_path": <opt>, "sparse_model_path": <opt>, "use_reranking": False}
    """

    name = "record_rag"

    # vendored models live at <spike>/models/<name> (this file is <spike>/verification/tools.py)
    _MODELS_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models"
    )

    def __init__(self, *, client: Any | None = None) -> None:
        self._client = client

    def _ensure_sdk(self):
        try:
            from lithrim_search_sdk import SearchClient, build_retrieval_manifest
        except Exception as exc:  # noqa: BLE001 - ImportError or heavy-dep load failure
            raise RuntimeError(
                "record_rag requires lithrim_search_sdk (onnxruntime/pinecone/pymongo). "
                "Install it: pip install -e <lithrim-backend>/lithrim_search_sdk. "
                "Use FakeRecordRagTool for offline tests."
            ) from exc
        return SearchClient, build_retrieval_manifest

    def _model_path(
        self, ref: dict, ref_key: str, env_keys: tuple[str, ...], default_name: str
    ) -> str | None:
        if ref.get(ref_key):
            return ref[ref_key]
        for k in env_keys:
            if os.environ.get(k):
                return os.environ[k]
        local = os.path.join(self._MODELS_DIR, default_name)
        return local if os.path.isdir(local) else None

    def _ensure_client(self, SearchClient, ref: dict):
        if self._client is not None:
            return self._client
        dense = self._model_path(
            ref,
            "dense_model_path",
            ("LITHRIM_DENSE_MODEL_PATH", "DENSE_MODEL_PATH"),
            "all-mpnet-base-v2",
        )
        sparse = self._model_path(
            ref,
            "sparse_model_path",
            ("LITHRIM_SPARSE_MODEL_PATH", "SPARSE_MODEL_PATH"),
            "Splade_PP_en_v2",
        )
        mongo = os.environ.get("MONGO_URI") or os.environ.get("MONGODB_URI")
        missing = []
        if not os.environ.get("PINECONE_API_KEY"):
            missing.append("PINECONE_API_KEY")
        if not mongo:
            missing.append("MONGO_URI (or MONGODB_URI)")
        if not dense:
            missing.append(
                "dense model (reference.dense_model_path / LITHRIM_DENSE_MODEL_PATH / vendored models/all-mpnet-base-v2)"
            )
        if not sparse:
            missing.append(
                "sparse model (reference.sparse_model_path / LITHRIM_SPARSE_MODEL_PATH / vendored models/Splade_PP_en_v2)"
            )
        if missing:
            raise RuntimeError(
                "record_rag not configured — missing: "
                + "; ".join(missing)
                + ". Note: the SDK's search() is hardwired to a Mongo-backed hybrid index; "
                "end-to-end retrieval also needs <JURISDICTION>_VDB_INDEX + "
                "<JURISDICTION>_AUGMENTED_COLLECTION env and a populated corpus."
            )
        self._client = SearchClient(
            pinecone_api_key=os.environ["PINECONE_API_KEY"],
            mongo_uri=mongo,
            dense_model_path=dense,
            sparse_model_path=sparse,
            use_reranking=bool(ref.get("use_reranking", False)),
        )
        return self._client

    def verify(self, claim: Claim, spec: VerificationSpec) -> VerificationResult:
        SearchClient, build_retrieval_manifest = self._ensure_sdk()
        ref = spec.reference
        client = self._ensure_client(SearchClient, ref)
        f = ref.get("filters") or {}
        query = str(claim.subject)
        results = client.search(
            query=query,
            jurisdiction=f.get("jurisdiction"),
            code_year=f.get("code_year"),
            categories=f.get("categories") or [],
            top_k=int(ref.get("top_k", 5)),
        )
        manifest = build_retrieval_manifest(
            results,
            query=query,
            context=query,
            metadata={
                "tool": self.name,
                "spec_version": spec.version,
                "filters": f,
                "as_of": ref.get("as_of"),
            },
        )
        return _rag_result(results, ref, manifest)


def _rag_result(results: list, ref: dict, manifest: dict) -> VerificationResult:
    """Shared verdict logic for RecordRag (real + fake): v0 retrieval-presence heuristic.

    conforms iff a pinned-reference hit clears `min_score`. This is the post-hoc
    v0; mid-loop judge-calls-tool semantic grounding is the graduation (deferred).
    """
    min_score = float(ref.get("min_score", 0.5))
    top = max((getattr(r, "score", 0.0) for r in results), default=0.0)
    conforms: bool | None = top >= min_score if results else None
    evidence = {
        "retrieved": len(results),
        "top_score": top,
        "min_score": min_score,
        "grounding": "retrieval_presence_v0",
    }
    return VerificationResult(conforms=conforms, evidence=evidence, manifest=manifest)


class _FakeResult:
    """Minimal SearchResult stand-in (id/score/metadata) for offline RecordRag tests."""

    def __init__(self, id: str, score: float, metadata: dict | None = None) -> None:
        self.id = id
        self.score = score
        self.metadata = metadata or {}


def _local_retrieval_manifest(results: list, *, query: str, metadata: dict) -> dict:
    """Offline mirror of lithrim_search_sdk.build_retrieval_manifest's determinism
    contract: stable order (score desc, id asc) + sha256 context hash."""
    ordered = sorted(results, key=lambda r: (-r.score, str(r.id)))
    return {
        "query": query,
        "retrieval_order": [r.id for r in ordered],
        "items": [{"id": r.id, "score": r.score, "metadata": r.metadata} for r in ordered],
        "context_hash": hashlib.sha256(query.encode("utf-8")).hexdigest(),
        "metadata": metadata,
    }


class FakeRecordRagTool(RecordRagTool):
    """Offline RecordRag over an in-memory PINNED corpus. Same interface + manifest
    shape as the real tool, no heavy deps. Deterministic by construction."""

    name = "record_rag"

    def __init__(self, corpus: dict[str, str]) -> None:
        super().__init__(client=None)
        self._corpus = dict(corpus)  # doc_id -> reference text

    def verify(self, claim: Claim, spec: VerificationSpec) -> VerificationResult:
        ref = spec.reference
        query = str(claim.subject)
        q = _norm(query)
        results = [
            _FakeResult(doc_id, self._overlap(q, _norm(text)), {"doc_id": doc_id})
            for doc_id, text in self._corpus.items()
        ]
        results = [r for r in results if r.score > 0.0]
        manifest = _local_retrieval_manifest(
            results,
            query=query,
            metadata={
                "tool": self.name,
                "spec_version": spec.version,
                "filters": ref.get("filters"),
                "fake": True,
            },
        )
        return _rag_result(results, ref, manifest)

    @staticmethod
    def _overlap(query: str, doc: str) -> float:
        qt = set(query.split())
        if not qt:
            return 0.0
        return round(len(qt & set(doc.split())) / len(qt), 6)
