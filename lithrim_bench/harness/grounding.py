"""Harness-side, post-hoc grounding: tool-checks that can flip a verdict.

The load-bearing exhibit is S-BS-7. The live council emits
``MEDICATION_NOT_IN_TRANSCRIPT`` as a confident false positive, citing — as its
proof of absence — the transcript line that *contains* the medication
(``zidovudine 300 MG Oral Tablet`` is verbatim in the transcript). No aggregation
lever separates this FP from the true defect ``FABRICATED_HISTORY``; both are
findings-first, fully evidenced, validated (REPORT_r3d_precheck_falsification).
The only lever that closes it reasons about span *content* — a presence-check.

WS-1: the contract set is no longer hardcoded. Contracts are **declared in the
ontology** (``data/ontology/clinical_v1.json`` → ``verification_contracts``) and
this module supplies the *executors* keyed by ``contract_type``. The med
presence-check's extraction strategy (med source, token floor, dosage regex, noise
tokens) is read from the declaration's ``params`` — it is data, not module
constants (WS-0 critique Q4.3). The severity→verdict re-score is the ontology's
``severity_map`` (Q4.2). Real / mid-loop tool grounding via JUTE / pinecone is WS-3.

S-BS-8 null-code findings (structural/artifact findings the live pipeline returns
with ``code=None``) cannot be keyed to a contract — they are skip-logged into an
"ungrounded" bucket, surfaced in the report, and kept in the active set; never
silently dropped.

S-BS-10 reference findings (coded with a known *out-of-snapshot* flag — the 4 fork
flags FABRICATED_CONSENT_SCOPE / MALAFFI_CODE_PROPAGATION / MISSING_DUAL_CODING /
WRONG_PATIENT_INFO) are not gradeable: the snapshot (contract-of-record) has not
blessed them. They are skip-logged into ``skipped_non_gradeable`` and — unlike
null-code findings — removed from the active set so they never silently drive the
verdict re-score. Surfaced in the report; never dropped. An unknown code (not a
declared flag at all) is left in active unchanged, as before.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .ontology import Ontology, VerificationContractDecl, load_ontology


@dataclass(frozen=True)
class Verdict:
    """The outcome of running one contract against one finding."""

    disproved: bool
    matched_token: str | None = None
    evidence: str | None = None
    reason: str = ""


@dataclass(frozen=True)
class GroundedResult:
    """The graded result after harness-side grounding.

    ``active`` is every finding that still contributes to the verdict (retained
    coded findings + null-code findings). ``suppressed`` are the disproved ones
    (removed from ``active``). ``ungrounded`` is the null-code subset (S-BS-8),
    a reporting view — those findings remain in ``active`` too.
    ``skipped_non_gradeable`` is the S-BS-10 reference subset (known out-of-snapshot
    codes) — skip-logged and removed from ``active`` so they never drive the
    re-score. ``weights`` is the ontology severity→weight map, carried so the
    report can score without re-importing a constant.

    ``floor_blocks`` is the WS-3 structural-floor direction (the inverse of
    ``suppressed``): each entry is a floor contract that ran over the *artifact*
    independent of any finding. On a real structural violation the council missed
    (tool ``conforms is False``), a BLOCK-driving finding is injected into
    ``active`` so the re-score flips PASS→BLOCK; the entry's ``injected_finding``
    is that finding. A floor contract that is inconclusive (``conforms is None`` —
    drift / no-compile / not-configured) is recorded with ``injected_finding=None``
    and NEVER flips the verdict (surfaced, never silent). A satisfied floor
    (``conforms is True``) is a no-op and not recorded — so ``floor_blocks == []``
    whenever no floor is declared OR every floor passes, and ``ground()`` is
    otherwise identical to its pre-WS-3 behaviour.
    """

    active: list[dict[str, Any]]
    suppressed: list[dict[str, Any]]
    ungrounded: list[dict[str, Any]]
    verdict: str
    original_verdict: str | None
    skipped_non_gradeable: list[dict[str, Any]] = field(default_factory=list)
    floor_blocks: list[dict[str, Any]] = field(default_factory=list)
    weights: dict[str, float] = field(default_factory=dict)
    result: dict[str, Any] = field(repr=False, default_factory=dict)
    case: dict[str, Any] = field(repr=False, default_factory=dict)


class VerificationContract:
    """A flag-keyed tool-check. ``check`` returns a :class:`Verdict`."""

    flag_code: str
    question: str
    version: str

    def check(self, finding: dict[str, Any], case: dict[str, Any]) -> Verdict:
        raise NotImplementedError


def _resolve_path(case: dict[str, Any], dotted: str) -> Any:
    """Resolve a dotted path (e.g. ``patient_profile.active_medications``)."""
    cur: Any = case
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _line_containing(transcript: str, token: str) -> str | None:
    for line in transcript.splitlines():
        if token in line.lower():
            return line.strip()
    return None


class PresenceCheck(VerificationContract):
    """Disprove an "X not in transcript" finding when X is in fact in the transcript.

    Built from a :class:`VerificationContractDecl`; the extraction strategy is the
    declaration's ``params`` (med source path, token floor, dosage regex, noise
    tokens). Conservative: only suppress on a *positive* presence match; never
    suppress on a failed extraction. The finding's evidence spans are cross-checked
    as corroboration when present (the S-BS-7 self-refuting span).
    """

    def __init__(self, decl: VerificationContractDecl) -> None:
        self.flag_code = decl.flag_code
        self.question = decl.question
        self.version = decl.version
        params = decl.params
        self._source = params["med_source"]
        self._token_min_len = int(params.get("token_min_len", 4))
        self._noise = set(params.get("noise_tokens") or [])
        self._dosage_re = re.compile(params["dosage_regex"], re.IGNORECASE)

    def _tokens(self, value: str) -> set[str]:
        cleaned = self._dosage_re.sub(" ", value).lower()
        return {
            tok
            for tok in re.split(r"[^a-z]+", cleaned)
            if len(tok) >= self._token_min_len and tok not in self._noise
        }

    def check(self, finding: dict[str, Any], case: dict[str, Any]) -> Verdict:
        transcript = case.get("transcript") or ""
        transcript_lc = transcript.lower()
        values = _resolve_path(case, self._source) or []

        for value in values:
            for token in self._tokens(value):
                if token in transcript_lc:
                    line = _line_containing(transcript, token)
                    spans = finding.get("_evidence_spans") or []
                    corroborated = any(token in (s.get("quote") or "").lower() for s in spans)
                    reason = (
                        f"medication '{token}' (from {self._source} '{value}') is "
                        f"present verbatim in the transcript"
                    )
                    if corroborated:
                        reason += (
                            "; the judge's own evidence span quotes the same line "
                            "it cites as proof of absence"
                        )
                    return Verdict(
                        disproved=True,
                        matched_token=token,
                        evidence=line,
                        reason=reason,
                    )
        return Verdict(
            disproved=False,
            reason="no source value resolved to a token present in the transcript",
        )


class KbGrounding(VerificationContract):
    """Disprove a confident-but-wrong council flag by GROUNDING its claim in the
    knowledge base — the S-BS-7 presence-check generalized from the transcript to
    the backend KB corpus (the paper's headline mechanism, the first Phase-3 slice).

    Where :class:`PresenceCheck` clears ``"X not in transcript"`` by finding X in the
    transcript, this clears ``"X violates policy P"`` (or ``"X is fabricated /
    unsupported"``) by finding the KB chunk that GROUNDS X — e.g. the HIPAA section
    the council claimed was violated actually PERMITS the disclosure, or the
    regulation/code the artifact cited is real and on-point. The heavy retrieval
    stays in lithrim-backend; this composes over ``GET :8002/v1/kb/{namespace}/search``
    via the promoted :class:`~lithrim_bench.verification.KbRagTool` (httpx lazy,
    injected ``http_client`` offline). Conservative: only suppress on a positive,
    score-clearing, corroborated KB hit (tool ``conforms is True``); a KB miss /
    error / below-threshold is inconclusive and NEVER clears the flag by silence.

    params = {"namespace": "hipaa",                      # required (KB catalog ns)
              "service": "http://localhost:8002",        # default :8002
              "claim_field": "detail" | "<finding key>", # what text to retrieve on
              "top_k": 5, "min_score": 0.0,
              "match": "claim_in_chunk" | None,           # corroboration predicate
              "api_key": <opt>}
    """

    contract_type = "kb_grounding"

    def __init__(
        self, decl: VerificationContractDecl, *, http_client: Any | None = None
    ) -> None:
        self.flag_code = decl.flag_code
        self.question = decl.question
        self.version = decl.version
        self._params = decl.params
        self._http_client = http_client

    def _reference(self) -> dict[str, Any]:
        p = self._params
        ref: dict[str, Any] = {"namespace": p["namespace"]}
        for key in ("service", "top_k", "min_score", "match", "api_key", "org_id"):
            if p.get(key) is not None:
                ref[key] = p[key]
        # the SUPPRESS direction grounds the claim -> expect a clearing PRESENT hit.
        ref["expect"] = "present"
        return ref

    def _claim_text(self, finding: dict[str, Any], case: dict[str, Any]) -> str:
        field_name = self._params.get("claim_field") or "detail"
        value = finding.get(field_name)
        if value:
            return str(value)
        # fall back to the finding's own detail/message, then the artifact text.
        for key in ("detail", "message", "rationale"):
            if finding.get(key):
                return str(finding[key])
        return str(_artifact_content(case) or "")

    def check(self, finding: dict[str, Any], case: dict[str, Any]) -> Verdict:
        from lithrim_bench.verification import (
            REFERENCE_CONFORMANCE,
            Claim,
            KbRagTool,
            VerificationSpec,
        )

        claim_text = self._claim_text(finding, case)
        ref = self._reference()
        spec = VerificationSpec(
            tool="kb_rag",
            applies_to_flags=(self.flag_code,),
            locus=self._params.get("locus", ""),
            reference=ref,
            version=self.version,
        )
        claim = Claim(
            claim_type=REFERENCE_CONFORMANCE,
            flag_code=self.flag_code,
            subject=claim_text,
            locus=self._params.get("locus", ""),
            source=case,
        )
        result = KbRagTool(http_client=self._http_client).verify(claim, spec)
        if result.conforms is True:
            ids = result.evidence.get("corroborated_ids") or []
            return Verdict(
                disproved=True,
                matched_token=str(ids[0]) if ids else None,
                evidence=f"KB[{ref['namespace']}] grounds the claim: {ids}",
                reason=(
                    f"claim grounded in KB namespace '{ref['namespace']}' "
                    f"(top_score={result.evidence.get('top_score')}); "
                    f"the council flag is disproven by retrieval"
                ),
            )
        return Verdict(
            disproved=False,
            reason=(
                "KB returned no score-clearing, corroborated grounding for the claim "
                f"(conforms={result.conforms}); flag stays open"
            ),
        )


# contract_type -> executor factory. This is the SUPPRESS registry (per-finding
# contracts that disprove an existing confident-but-wrong finding). The structural
# FLOOR direction (artifact-level contracts that inject a BLOCK the council missed)
# is a categorically different shape — it is keyed in ``_FLOOR_CONTRACT_TYPES`` and
# run by ``_run_floor``, not here.
#
# ``kb_grounding`` (WS-7b) is the KB-grounded suppress executor — the S-BS-7
# presence-check generalized to the backend KB. It needs the injected ``http_client``
# (it composes over live :8002), so ``_build_contract`` threads it in; ``PresenceCheck``
# is pure-stdlib and ignores it.
_CONTRACT_EXECUTORS = {"presence_check": PresenceCheck, "kb_grounding": KbGrounding}
_HTTP_CONTRACT_TYPES = {"kb_grounding"}

# contract_type set for the WS-3 structural floor. These resolve to the promoted
# ``lithrim_bench.verification`` tools (imported lazily in ``_run_floor`` so this
# module's own import stays stdlib-only — no httpx/dspy pulled). KB / vector floor
# executors land in WS-3b.
_FLOOR_CONTRACT_TYPES = {"structural_jute", "jute_gen"}


def _build_contract(
    decl: VerificationContractDecl, *, http_client: Any | None = None
) -> VerificationContract:
    factory = _CONTRACT_EXECUTORS.get(decl.contract_type)
    if factory is None:
        raise ValueError(f"no executor registered for contract_type {decl.contract_type!r}")
    # HTTP-composing suppress executors (kb_grounding) reuse the injected client;
    # pure-stdlib ones (presence_check) take only the declaration.
    if decl.contract_type in _HTTP_CONTRACT_TYPES:
        return factory(decl, http_client=http_client)
    return factory(decl)


def _artifact_content(case: dict[str, Any]) -> Any:
    """The first artifact's content (the thing a structural floor validates), or None."""
    artifacts = case.get("artifacts") or []
    if not artifacts or not isinstance(artifacts[0], dict):
        return None
    return artifacts[0].get("content")


def _run_floor(decl: VerificationContractDecl, case: dict[str, Any], *, http_client: Any | None):
    """Run one structural-floor contract over the case artifact.

    Adapts the ontology's ``VerificationContractDecl`` into the promoted
    ``verification`` toolbox's ``VerificationSpec`` + ``Claim`` and runs the tool,
    returning its tri-state ``VerificationResult`` (or ``None`` when the case has no
    artifact to validate). ``http_client`` is injectable (the ``grade_replay`` /
    ``grade_live`` mirror): a fake/replay client for offline tests, ``None`` for the
    live ``:3031`` path (the tool creates an ``httpx.Client`` lazily — which requires
    the optional ``[verification]`` extra).

    The committed/reproducible floor uses ``contract_type="jute_gen"`` with a
    ``pinned_template`` (read from the repo, applied in-memory via
    ``/mappings/test-template`` — no DB write, no :3031 mutation). ``structural_jute``
    with a ``mapping_selector`` is the live-mapping convenience path.
    """
    artifact = _artifact_content(case)
    if artifact is None:
        return None

    from lithrim_bench.verification import (
        STRUCTURAL_CONFORMANCE,
        Claim,
        JuteGenValidatorTool,
        StructuralJuteTool,
        VerificationSpec,
    )

    params = decl.params
    locus = params.get("locus", "")
    if decl.contract_type == "jute_gen":
        tool = JuteGenValidatorTool(http_client=http_client)
        reference = {
            "service": params["service"],
            "artifact_kind": params["artifact_kind"],
            "pinned_template": params["pinned_template"],
        }
        if params.get("pinned_template_sha256"):
            reference["pinned_template_sha256"] = params["pinned_template_sha256"]
    elif decl.contract_type == "structural_jute":
        tool = StructuralJuteTool(http_client=http_client)
        reference = {
            "service": params["service"],
            "mapping_selector": params["mapping_selector"],
            "artifact_kind": params["artifact_kind"],
        }
        if params.get("pinned_content_sha256"):
            reference["pinned_content_sha256"] = params["pinned_content_sha256"]
    else:  # pragma: no cover - guarded by the partition in ground()
        raise ValueError(f"no floor executor for contract_type {decl.contract_type!r}")

    spec = VerificationSpec(
        tool=decl.contract_type,
        applies_to_flags=(decl.flag_code,),
        locus=locus,
        reference=reference,
        version=decl.version,
    )
    claim = Claim(
        claim_type=STRUCTURAL_CONFORMANCE,
        flag_code=decl.flag_code,
        subject=artifact,
        locus=locus,
        source=case,
    )
    return tool.verify(claim, spec)


def ground(
    result: dict[str, Any],
    case: dict[str, Any],
    *,
    ontology: Ontology | None = None,
    http_client: Any | None = None,
) -> GroundedResult:
    """Run every matching contract over the result's findings; re-score the verdict.

    Contracts and the severity map come from ``ontology`` (default: the committed
    clinical ontology). Disproved findings are removed from the active set.
    Null-code findings (S-BS-8) are skip-logged into ``ungrounded`` and retained in
    ``active``. Reference findings (S-BS-10 — coded with a known non-gradeable flag)
    are skip-logged into ``skipped_non_gradeable`` and removed from ``active`` so
    they are never scored. Coded findings with no matching contract are retained
    unchanged.

    WS-3 structural floor: after the per-finding suppress pass, any floor contract
    declared in the ontology (``contract_type`` in ``_FLOOR_CONTRACT_TYPES``) runs
    over the *artifact*. A real structural violation the council missed
    (``conforms is False``) injects a BLOCK-driving finding into ``active`` so the
    re-score flips PASS→BLOCK. ``http_client`` is injectable for the floor's apply
    (a fake/replay client offline; ``None`` => the live ``:3031`` path). When the
    ontology declares NO floor contract — the committed clinical default — the floor
    pass is a no-op and the result is identical to the pre-WS-3 ``ground()`` (with
    ``floor_blocks == []``).
    """
    ontology = ontology or load_ontology()
    suppress_decls = [d for d in ontology.contracts if d.contract_type in _CONTRACT_EXECUTORS]
    floor_decls = [d for d in ontology.contracts if d.contract_type in _FLOOR_CONTRACT_TYPES]
    unknown = [
        d
        for d in ontology.contracts
        if d.contract_type not in _CONTRACT_EXECUTORS
        and d.contract_type not in _FLOOR_CONTRACT_TYPES
    ]
    if unknown:
        raise ValueError(f"no executor registered for contract_type {unknown[0].contract_type!r}")
    contracts = {
        decl.flag_code: _build_contract(decl, http_client=http_client)
        for decl in suppress_decls
    }
    semantic_evidence = {
        ev.get("violation_code"): ev for ev in (result.get("semantic") or {}).get("evidence", [])
    }
    findings = result.get("findings") or []

    active: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []
    ungrounded: list[dict[str, Any]] = []
    skipped_non_gradeable: list[dict[str, Any]] = []

    for finding in findings:
        code = finding.get("code")
        if code is None:
            ungrounded.append(finding)
            active.append(finding)
            continue
        if ontology.is_reference(code):
            # S-BS-10: a known out-of-snapshot flag — skip-logged, never scored.
            skipped_non_gradeable.append(finding)
            continue
        contract = contracts.get(code)
        if contract is None:
            active.append(finding)
            continue
        enriched = dict(finding)
        ev = semantic_evidence.get(code)
        if ev is not None:
            enriched["_evidence_spans"] = ev.get("spans")
        verdict = contract.check(enriched, case)
        if verdict.disproved:
            suppressed.append({"finding": finding, "verdict": verdict, "contract": contract})
        else:
            active.append(finding)

    # WS-3 structural floor (the inverse direction): inject a BLOCK the council missed.
    floor_blocks: list[dict[str, Any]] = []
    for decl in floor_decls:
        vr = _run_floor(decl, case, http_client=http_client)
        if vr is None:
            continue
        if vr.conforms is False:
            injected = {
                "code": decl.params["inject_flag_code"],
                "severity": decl.params["inject_severity"],
                "detail": (
                    f"structural floor: artifact violates pinned {decl.contract_type} "
                    f"contract ({decl.params.get('artifact_kind')})"
                ),
                "_floor": True,
                "_contract_version": decl.version,
            }
            active.append(injected)
            floor_blocks.append({"decl": decl, "result": vr, "injected_finding": injected})
        elif vr.conforms is None:
            # inconclusive (drift / no-compile / not-configured) — surfaced, never flips.
            floor_blocks.append({"decl": decl, "result": vr, "injected_finding": None})

    return GroundedResult(
        active=active,
        suppressed=suppressed,
        ungrounded=ungrounded,
        skipped_non_gradeable=skipped_non_gradeable,
        floor_blocks=floor_blocks,
        verdict=ontology.severity_map.rescore(active),
        original_verdict=result.get("verdict"),
        weights=dict(ontology.severity_map.weights),
        result=result,
        case=case,
    )
