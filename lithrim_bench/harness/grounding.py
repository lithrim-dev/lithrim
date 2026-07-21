"""Harness-side, post-hoc grounding: tool-checks that can flip a verdict.

The load-bearing exhibit is S-BS-7. The live council emits
``MEDICATION_NOT_IN_TRANSCRIPT`` as a confident false positive, citing — as its
proof of absence — the transcript line that *contains* the medication
(``zidovudine 300 MG Oral Tablet`` is verbatim in the transcript). No aggregation
lever separates this FP from the true defect ``FABRICATED_HISTORY``; both are
findings-first, fully evidenced, validated (REPORT_r3d_precheck_falsification).
The only lever that closes it reasons about span *content* — a presence-check.

WS-1: the contract set is no longer hardcoded. Contracts are **declared in the
ontology** (``packs/healthcare/ontology.json`` → ``verification_contracts``) and
this module supplies the *executors* keyed by ``contract_type``. The med
presence-check's extraction strategy (med source, token floor, extraction regex, noise
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

import contextlib
import hashlib
import re
from dataclasses import dataclass, field, replace
from functools import lru_cache
from typing import Any

from .ontology import Ontology, VerificationContractDecl, load_ontology


@dataclass(frozen=True)
class Verdict:
    """The outcome of running one contract against one finding.

    ``terminology_edition`` (REL-OPS-1 O2, record-only) is the terminology release that
    decided a ``terminology_subsumption`` execution — the edition string when an
    ``edition_op`` is configured and answers, the honest ``"unrecorded"`` otherwise, and
    ``None`` for every non-terminology contract (so their record shapes are unchanged)."""

    disproved: bool
    matched_token: str | None = None
    evidence: str | None = None
    reason: str = ""
    terminology_edition: str | None = None


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

    ``coverage`` (FLOOR-COVERAGE-1) is a PURELY DERIVED, read-only provenance summary
    computed AFTER ``active``/``suppressed``/``floor_blocks`` are finalized — it labels
    every surviving finding with a coverage tag and stamps ``floor_backstopped`` (False
    when a BLOCK rests solely on judge-only findings the deterministic floor never
    grounded). It never perturbs the grade: ``active``/``suppressed``/``verdict`` are
    byte-identical with or without it, so it stays OUT of the signed grade digest.
    """

    active: list[dict[str, Any]]
    suppressed: list[dict[str, Any]]
    ungrounded: list[dict[str, Any]]
    verdict: str
    original_verdict: str | None
    skipped_non_gradeable: list[dict[str, Any]] = field(default_factory=list)
    floor_blocks: list[dict[str, Any]] = field(default_factory=list)
    skipped_malformed: list[dict[str, Any]] = field(default_factory=list)
    weights: dict[str, float] = field(default_factory=dict)
    coverage: dict[str, Any] = field(default_factory=dict)
    # READ-ATTRIB-1: the same rescore over the finding set this grade would have had if the
    # floor had never run — so ``verdict`` vs ``verdict_no_floor`` isolates the floor's effect.
    verdict_no_floor: str | None = None
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
    declaration's ``params`` (med source path, token floor, extraction regex, noise
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


# A small, domain-neutral English stopword set: the connective/function words that carry
# no asserted claim (so an answer made entirely of them grounds vacuously). Kept deliberately
# minimal — only words that are never themselves a faithfulness claim — so we don't drop a real
# content token. The numeric-salience rule below means figures ("100","20") are ALWAYS salient.
_STOPWORDS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "can", "did", "do",
        "does", "for", "from", "had", "has", "have", "her", "here", "his", "how", "into", "its",
        "may", "not", "now", "off", "our", "out", "per", "she", "should", "so", "some", "such",
        "than", "that", "the", "their", "them", "then", "there", "these", "they", "this", "those",
        "through", "thus", "to", "too", "was", "were", "what", "when", "where", "which", "while",
        "who", "whom", "why", "will", "with", "would", "yes", "you", "your", "yours",
    }
)


def _light_stem(token: str) -> str:
    """A LIGHT morphology normalizer so ``includes``≈``include`` and ``storing``≈``store``
    match without a real stemmer. Strip ``ing``/``ed`` first, then a single trailing ``s``
    (the plural ``s``: ``includes``→``include`` — NOT an ``es`` strip, which would over-cut
    ``includes``→``includ`` and DESYNC from the source's ``include``). Never stem below 3
    chars (so ``is``/``as`` stay intact). Both the answer and the source pass through this,
    so the normalization is symmetric by construction."""
    for suffix in ("ing", "ed"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    if token.endswith("s") and not token.endswith("ss") and len(token) - 1 >= 3:
        return token[:-1]
    return token


class SourceGrounding(VerificationContract):
    """The answer⊆source faithfulness floor — the S-BS-7 presence-check GENERALIZED.

    Where :class:`PresenceCheck` clears ``"X not in transcript"`` by finding X in the
    transcript, this clears ``"the answer contradicts / asserts beyond the source"`` by
    proving the inverse: EVERY salient claim the ANSWER makes is present in the SOURCE.
    If the answer says nothing the source does not also state, it can neither contradict
    the source (SOURCE_CONTRADICTION) nor assert beyond it (UNSUPPORTED_ASSERTION) — the
    finding is disproved.

    Conservative / anti-masking by construction: SUPPRESS ONLY on FULL grounding — every
    salient (stemmed) answer token must appear in the (stemmed) source token set. ANY
    ungrounded salient token ⇒ the finding STANDS (the ungrounded tokens ARE the potential
    fabrication). A real fabrication (a claim absent from the source — "unlimited storage,
    lifetime guarantee") is therefore NEVER cleared. Never raises on a missing field: an
    absent artifact/source is treated as ``""`` → nothing grounds → ``disproved=False``
    (never clear by silence).

    Pure-stdlib / ``in_process`` (no network, no LM). All params optional:
      params = {"source_path":  "transcript",   # dotted path to the source material
                "token_min_len": 4,              # min len for an ALPHA token to be salient
                "noise_tokens":  []}             # extra tokens to treat as non-salient
    """

    contract_type = "source_grounding"

    def __init__(self, decl: VerificationContractDecl) -> None:
        self.flag_code = decl.flag_code
        self.question = decl.question
        self.version = decl.version
        params = decl.params
        self._source_path = params.get("source_path", "transcript")
        self._token_min_len = int(params.get("token_min_len", 4))
        self._noise = {t.lower() for t in (params.get("noise_tokens") or [])}

    def _salient_answer_tokens(self, answer: str) -> dict[str, str]:
        """The salient tokens of the answer, mapped ``stem -> surface`` (the surface form is
        kept for a human-readable reason). Numeric tokens are ALWAYS salient ("100"/"20"); an
        alpha token is salient iff len ≥ token_min_len and not a stopword / declared noise.
        Light-stemmed for morphology robustness — the stem is the grounding-comparison key."""
        out: dict[str, str] = {}
        for tok in re.split(r"[^a-z0-9]+", answer.lower()):
            if not tok:
                continue
            if tok.isdigit():
                out.setdefault(tok, tok)
                continue
            if len(tok) < self._token_min_len:
                continue
            if tok in _STOPWORDS or tok in self._noise:
                continue
            out.setdefault(_light_stem(tok), tok)
        return out

    def _source_token_set(self, source: str) -> set[str]:
        """Every token of the source, stemmed — the grounding vocabulary an answer token must
        hit. Digits kept verbatim; alpha tokens light-stemmed to match the answer side."""
        out: set[str] = set()
        for tok in re.split(r"[^a-z0-9]+", source.lower()):
            if not tok:
                continue
            out.add(tok if tok.isdigit() else _light_stem(tok))
        return out

    def check(self, finding: dict[str, Any], case: dict[str, Any]) -> Verdict:
        answer = (
            _artifact_content(case)
            or case.get("artifact")
            or case.get("artifact_text")
            or ""
        )
        source = (
            _resolve_path(case, self._source_path)
            or case.get("transcript")
            or case.get("context")
            or ""
        )
        salient = self._salient_answer_tokens(str(answer))
        source_tokens = self._source_token_set(str(source))

        # The ungrounded surface forms — the potential fabrication — sorted for determinism.
        ungrounded = sorted(surface for stem, surface in salient.items() if stem not in source_tokens)
        # Conservative: with NO salient tokens, nothing is grounded -> never clear by silence.
        if not salient or ungrounded:
            sample = ungrounded[:5] if ungrounded else ["<no salient claim grounded>"]
            return Verdict(
                disproved=False,
                # ``evidence`` carries the FULL ungrounded set for audit; ``reason`` a ≤5 sample.
                evidence=", ".join(ungrounded) if ungrounded else None,
                reason=(
                    f"answer contains content absent from the source: {sample} — "
                    f"the finding stands"
                ),
            )
        grounded = sorted(salient.values())
        return Verdict(
            disproved=True,
            matched_token=next(iter(grounded), None),
            evidence=", ".join(grounded[:5]),
            reason=(
                "every salient claim in the answer is present in the source — the answer "
                f"asserts nothing the source does not state; {self.flag_code} is disproved"
            ),
        )


def _containment_norm(value: Any) -> str:
    """The verbatim-containment surface: lowercase, non-alphanumeric → space,
    whitespace-collapsed — so case / punctuation / line-wrap differences between a
    judge's quote and the source never break a genuinely verbatim match."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())).strip()


class EvidencePresence(VerificationContract):
    """The evidence-integrity gate (LAYER2-SUPPRESS-1): disprove a finding whose OWN
    evidence spans are verbatim source text.

    A finding that claims a defect *of the artifact* (an internal inconsistency, a
    hallucinated detail) but whose flagged evidence is a verbatim quote of the SOURCE
    refutes its own type — the judge is citing the source itself as the proof. Measured
    on the clinverdict 173-record clean run (2026-07-02): TP-safe on
    INTERNAL_INCONSISTENCY (13 FP / 0 of 5 golds) + HALLUCINATED_DETAIL (7 FP / 0 of 7);
    NOT declarable on SOURCE_CONTRADICTION / VALUE_MISMATCH, where a real defect's
    transcript-side quote fires it (11/19 golds) — a weak-supervision LF whose scope the
    corpus referees, per code.

    Pure-stdlib / ``in_process``. Conservative on every axis (never clear by silence):
    no spans, an absent source, or every quote below ``min_quote_chars`` ⇒ stands.
    ``mode="all"`` (the default) requires EVERY span to be a long-enough verbatim source
    quote; ``mode="any"`` fires when at least one is — the declaration opts into the
    looser form explicitly, the default stays the most conservative.

      params = {"source_path": "transcript",  # dotted; default transcript→context fallback
                "min_quote_chars": 12,         # min NORMALIZED quote length to count
                "mode": "all" | "any"}
    """

    contract_type = "evidence_presence"

    def __init__(self, decl: VerificationContractDecl) -> None:
        self.flag_code = decl.flag_code
        self.question = decl.question
        self.version = decl.version
        params = decl.params
        self._source_path = params.get("source_path")
        self._min_chars = int(params.get("min_quote_chars", 12))
        if self._min_chars < 4:
            # below any meaningful verbatim claim — a 1-char "match" must never clear a
            # finding; rejected at construction so the author-time gate 422s it.
            raise ValueError(
                f"evidence_presence min_quote_chars must be >= 4, got {self._min_chars}"
            )
        mode = params.get("mode", "all")
        if mode not in ("all", "any"):
            raise ValueError(f"evidence_presence mode must be 'all' or 'any', got {mode!r}")
        self._mode = mode

    def check(self, finding: dict[str, Any], case: dict[str, Any]) -> Verdict:
        if self._source_path:
            source = _resolve_path(case, self._source_path) or ""
        else:
            source = case.get("transcript") or case.get("context") or ""
        source_n = _containment_norm(source)
        spans = finding.get("_evidence_spans") or []
        quotes = [str((s.get("quote") if isinstance(s, dict) else s) or "") for s in spans]
        quotes = [q for q in quotes if q.strip()]
        if not source_n or not quotes:
            return Verdict(
                disproved=False,
                reason="no source text / no evidence spans; inconclusive — never clear by silence",
            )
        normed = [(q, _containment_norm(q)) for q in quotes]
        matched = [
            (q, qn) for q, qn in normed if len(qn) >= self._min_chars and qn in source_n
        ]
        fires = bool(matched) and (self._mode == "any" or len(matched) == len(normed))
        if fires:
            quote = matched[0][0]
            return Verdict(
                disproved=True,
                evidence=quote,
                reason=(
                    f"{len(matched)}/{len(normed)} flagged evidence span(s) are verbatim "
                    f"source text (mode={self._mode}, min_quote_chars={self._min_chars}) — "
                    f"the finding cites the source itself as its evidence, refuting the "
                    f"claimed {self.flag_code}"
                ),
            )
        return Verdict(
            disproved=False,
            reason=(
                f"{len(matched)}/{len(normed)} span(s) matched the source under "
                f"mode={self._mode}; the finding stands"
            ),
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

    def __init__(self, decl: VerificationContractDecl, *, http_client: Any | None = None) -> None:
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


class WebSearchGrounding(VerificationContract):
    """The web-search reference connector as a suppress-shaped contract (CONN-WEBSEARCH-1) —
    that BY CONSTRUCTION CAN NEVER CLEAR A FINDING.

    Unlike :class:`KbGrounding`, which clears a confident-but-wrong flag on a positive,
    score-clearing, corroborated KB hit, this contract is structurally NON-AUTHORITATIVE: web
    results are unverifiable, so it ALWAYS returns the non-suppressing verdict
    (``disproved=False``). It runs the search, ATTACHES the retrieved citations/snippets +
    ``web_support`` to the verdict's evidence/reason for the SME / withstands-gate to weigh, and
    NEVER suppresses — present, absent, or erroring. This structurally enforces spec §4's
    "evidence to weigh, not an authoritative floor that overrides the verdict" — a stronger
    guarantee than a convention that one must not bind it to high-stakes flags. It can never flip
    a verdict.

    params = {"query": "<claim/query selector>",            # required (the SME-pinned query)
              "service": "http://localhost:8585",           # default :8585 / env
              "top_k": 5, "api_key": <opt>}
    """

    contract_type = "web_search"

    def __init__(self, decl: VerificationContractDecl, *, http_client: Any | None = None) -> None:
        self.flag_code = decl.flag_code
        self.question = decl.question
        self.version = decl.version
        self._params = decl.params
        self._http_client = http_client

    def _reference(self, finding: dict[str, Any]) -> dict[str, Any]:
        p = self._params
        ref: dict[str, Any] = {"query": self._query(finding)}
        for key in ("service", "top_k", "min_score", "api_key"):
            if p.get(key) is not None:
                ref[key] = p[key]
        return ref

    def _query(self, finding: dict[str, Any]) -> str:
        if self._params.get("query"):
            return str(self._params["query"])
        field_name = self._params.get("claim_field") or "detail"
        for key in (field_name, "detail", "message", "rationale"):
            if finding.get(key):
                return str(finding[key])
        return ""

    def check(self, finding: dict[str, Any], case: dict[str, Any]) -> Verdict:
        from lithrim_bench.verification import (
            REFERENCE_CONFORMANCE,
            Claim,
            VerificationSpec,
            WebSearchTool,
        )

        ref = self._reference(finding)
        spec = VerificationSpec(
            tool="web_search",
            applies_to_flags=(self.flag_code,),
            locus=self._params.get("locus", ""),
            reference=ref,
            version=self.version,
        )
        claim = Claim(
            claim_type=REFERENCE_CONFORMANCE,
            flag_code=self.flag_code,
            subject=ref["query"],
            locus=self._params.get("locus", ""),
            source=case,
        )
        result = WebSearchTool(http_client=self._http_client).verify(claim, spec)
        citations = result.evidence.get("citations") or []
        support = result.evidence.get("web_support")
        # NON-AUTHORITATIVE BY CONSTRUCTION: never suppress. Attach the web evidence to the
        # verdict (so the SME / withstands-gate can weigh it); the finding STAYS open regardless.
        return Verdict(
            disproved=False,
            evidence=f"web_search citations={citations}" if citations else None,
            reason=(
                f"web_search is non-authoritative: attached {len(citations)} citation(s) "
                f"(web_support={support}); evidence to weigh, the flag stays open"
            ),
        )


def _truthy_match(result: Any, key: str | None) -> bool:
    """The corroboration predicate over an MCP tool result: a named key's truthiness, else the
    result's own truthiness (a non-empty list/dict/string)."""
    if key is not None:
        if isinstance(result, dict):
            return bool(result.get(key))
        if isinstance(result, (list, tuple)):
            return any(isinstance(x, dict) and x.get(key) for x in result)
        return False
    if isinstance(result, (list, tuple, dict, str)):
        return len(result) > 0
    return bool(result)


def _jute_client() -> Any:
    """The :3031 JUTE-apply seam for CRITERION-JUTE-1a's pinned arg-shaping — an
    ``EtlpJuteClient`` whose ``test_template`` applies the pinned template IN-MEMORY (no DB write,
    no :3031 mutation), exactly the seam ``jute_gen`` uses. Isolated in a factory so tests inject a
    fake (:3031 is not required offline). The live client creates its ``httpx.Client`` lazily (the
    optional ``[verification]`` extra), so importing it is cheap and networkless until first apply.

    The base URL honours ``LITHRIM_JUTE_URL`` (the deployment mapper URL — e.g.
    ``http://jute:3000`` inside the container), falling back to the ``etlp_jute`` manifest default
    (``localhost:3031``, the SINGLE source of the default — JUTE-ADDON-1) when unset — byte-identical
    for offline/test callers, which inject a fake anyway. This retires the localhost:3031→jute:3000
    port-forward: the live floor now reaches the mapper the deployment configured, so a dead-mapper
    None from ``_shape_arguments`` is a real reachability failure, not a hostname mismatch."""
    import os

    from lithrim_bench.harness import plugins
    from lithrim_bench.verification import EtlpJuteClient

    base_url = os.environ.get("LITHRIM_JUTE_URL") or plugins.etlp_jute_default_base_url()
    return EtlpJuteClient(base_url=base_url)


class McpCallGrounding(VerificationContract):
    """TOOL-AUTHOR-1: the GENERIC MCP-tool suppress executor — wire ANY authored MCP tool
    (web-scraper, terminology, KB) into a judge's flag with no per-tool Python. Resolves the bound
    tool via :func:`plugins.resolve_tool` (authored ∪ pack ∪ core, per-workspace, license-gated),
    opens the core :class:`McpStdioClient` over its stdio MCP transport, invokes the pinned
    ``call`` with ``arguments``, and maps the result by **authority tier**:

      - ``advisory`` (default) — attach the result as evidence, ``disproved=False`` ALWAYS (the
        finding stays open; the withstands-gate weighs the evidence — the moat: agent narrates,
        floor decides). The web-scraper/KB shape.
      - ``corroborated`` — clear the finding (``disproved=True``) ONLY on a positive ``match``,
        NEVER by silence (a miss/absence/error leaves the finding standing).

    Graceful-absent (non-negotiable): an unresolvable tool, a tool with no stdio transport, or an
    unreachable server → ``disproved=False`` (the finding STANDS), no 500, no silent flip. The
    ``tool.api_connector`` (httpx) transport is the owner's next integration — it lands as another
    branch here, not a rewrite.

    params = {"tool": "<authored/declared tool id>",   # required
              "call": "<mcp tool name>",               # required (e.g. search / scrape)
              "arguments": {...},                       # pinned args (not model-authored)
              "authority": "advisory" | "corroborated",
              "match": "<result key>"}                  # corroborated predicate
    """

    contract_type = "mcp_call"

    def __init__(self, decl: VerificationContractDecl, *, http_client: Any | None = None) -> None:
        self.flag_code = decl.flag_code
        self.question = decl.question
        self.version = decl.version
        self._params = decl.params

    def check(self, finding: dict[str, Any], case: dict[str, Any]) -> Verdict:
        from lithrim_bench.harness import plugins

        p = self._params
        tool_id, call = p.get("tool"), p.get("call")
        if not tool_id or not call:
            return Verdict(disproved=False, reason="mcp_call: missing tool/call (inconclusive)")
        manifest = plugins.resolve_tool(tool_id)
        if manifest is None:
            return Verdict(
                disproved=False,
                reason=f"mcp_call: tool {tool_id!r} not available (not_applicable; finding stands)",
            )
        mcp = (manifest.service or {}).get("mcp") or {}
        if not mcp.get("command"):
            return Verdict(
                disproved=False,
                reason=f"mcp_call: tool {tool_id!r} has no stdio MCP transport yet (not_applicable)",
            )
        # CRITERION-JUTE-1a: shape the tool arguments — a pinned per-case JUTE transform if declared,
        # else the static dict (today's byte-identical path). A drifted transform REFUSES (None):
        # never grade through it — the finding stands.
        arguments = self._shape_arguments(case, finding)
        if arguments is None:
            return Verdict(
                disproved=False,
                reason=(
                    "mcp_call: arguments_jute hash mismatch (pinned transform drifted); "
                    "refusing to grade — finding stands"
                ),
            )

        from lithrim_bench.verification.mcp_client import McpStdioClient

        client = McpStdioClient(command=mcp.get("command"), args=mcp.get("args", []))
        try:
            result = client.call_tool(call, arguments)
        except Exception as exc:  # noqa: BLE001 — unreachable server: finding stands, never a 500
            return Verdict(
                disproved=False, reason=f"mcp_call: {tool_id}.{call} unreachable ({exc}); finding stands"
            )
        finally:
            with contextlib.suppress(Exception):
                client.close()

        evidence = f"{tool_id}.{call} -> {str(result)[:280]}"
        if (p.get("authority") or "advisory").lower() != "corroborated":
            return Verdict(
                disproved=False, evidence=evidence,
                reason="mcp_call advisory: evidence attached, flag stays open (non-authoritative)",
            )
        matched = _truthy_match(result, p.get("match"))
        return Verdict(
            disproved=bool(matched),
            evidence=evidence,
            reason=(
                "mcp_call corroborated: positive match, finding disproved"
                if matched
                else "mcp_call corroborated: no positive match; finding stands (never cleared by silence)"
            ),
        )

    def _shape_arguments(self, case: dict[str, Any], finding: dict[str, Any]) -> dict | None:
        """CRITERION-JUTE-1a: the argument source for the tool call.

        - No ``arguments_jute`` -> ``params.get("arguments") or {}`` (today's behaviour, byte-identical
          for every existing contract — those carry no ``arguments_jute``, so this is the only branch
          they reach and the moat is 0-delta on the current corpus).
        - ``arguments_jute`` present -> HASH-VERIFY it against ``arguments_jute_sha256`` FIRST; on
          mismatch return ``None`` (the REFUSE sentinel — never grade through a drifted transform,
          mirroring the ``jute_gen`` ``pinned_template_sha256`` refusal). On match, apply the pinned
          JUTE to ``{case, finding}`` in-memory via the same :3031 ``test_template`` seam ``jute_gen``
          uses (no DB write) and return the shaped arguments object. If the transform fails to compile
          or does not yield an object (should be impossible after the corpus gate, but defensively),
          return ``None`` so the finding stands rather than grade through a broken shape.
        """
        p = self._params
        jute = p.get("arguments_jute")
        if not jute:
            return p.get("arguments") or {}
        want = p.get("arguments_jute_sha256")
        if not want or hashlib.sha256(jute.encode("utf-8")).hexdigest() != want:
            return None  # drift: refuse, finding stands
        try:
            applied = _jute_client().test_template(jute, {"case": case, "finding": finding})
        except Exception:  # noqa: BLE001 — a dead :3031 must not grade through; finding stands
            return None
        if not isinstance(applied, dict) or applied.get("compiled") is False:
            return None
        output = applied.get("output")
        return output if isinstance(output, dict) else None


def _terminology_edition(client: Any, edition_op: Any) -> str:
    """REL-OPS-1 O2: the terminology release/edition that decided this grounding execution.

    Record-only and fail-honest: no configured op, an erroring op, or an answer whose release
    identifier cannot be read from a NAMED key stamps ``"unrecorded"`` — never a guess, and
    never an exception (an edition-lookup failure must not change any verdict). Called once
    per tool session, AFTER the grounding calls, so it cannot perturb them."""
    if not edition_op:
        return "unrecorded"
    try:
        result = client.call_tool(str(edition_op), {})
    except Exception:  # noqa: BLE001 — never fail the grounding over the edition lookup
        return "unrecorded"
    if isinstance(result, str) and result.strip():
        return result.strip()
    if isinstance(result, (int, float)) and not isinstance(result, bool):
        return str(result)
    candidates = [result] if isinstance(result, dict) else result if isinstance(result, list) else []
    for item in candidates[:1]:
        if not isinstance(item, dict):
            continue
        for key in ("edition", "release", "version", "release_date", "releaseDate"):
            if item.get(key):
                return str(item[key])
    return "unrecorded"


class TerminologySubsumption(VerificationContract):
    """REPRO-1 R4c: the CORE-GENERIC terminology-subsumption suppress executor — ground the
    FLAGGED SPAN's term(s) against the case's record concepts by is-a subsumption through a
    USER-CONNECTED ``kind:tool`` terminology server. The domain lives entirely in DATA: the
    tool id, the record path, the op names, and any term-extraction regex are SME-authored
    params; the subsumption relation comes from the connected ontology, never from code. (The
    healthcare pack's ``snomed_subsumption`` remains its clinically-tuned sibling — SOAP/PMH
    extraction; this one is the clean-workspace path.)

    Span-driven BY CONSTRUCTION (the SPAN-BIND-1 lesson): the candidate terms ARE the
    finding's own evidence-span quotes (optionally narrowed by ``term_regex``) — this oracle
    can only speak to what the finding actually flagged; there is no flag-code-level clear.

    Conservative (never clears by silence): suppress ONLY when there ARE candidates and EVERY
    candidate resolves to a concept that is == or subsumed-by a record concept. No spans, an
    empty record, an unresolvable term, an un-subsumed term, or an absent/unreachable tool →
    the finding STANDS.

    REL-OPS-1 O2 (record-only): every execution stamps ``terminology_edition`` on its
    verdict — the release identifier returned by the ``edition_op`` named in the contract
    params or the tool's service config, else ``"unrecorded"`` (a failed lookup never
    changes the verdict; change detection / golden re-run triggering is a later cut).

    params = {"tool": "<kind:tool terminology id>",     # required (ToolBuilder-authored)
              "record_path": "<case path of record terms>",  # required
              "term_regex": "<optional candidate extractor over the span quote>",
              "search_call": "search", "subsumes_call": "subsumed_by",  # op names (data)
              "edition_op": "<optional release/edition lookup op>"}     # O2 pinning
    """

    contract_type = "terminology_subsumption"

    def __init__(self, decl: VerificationContractDecl, *, http_client: Any | None = None) -> None:
        self.flag_code = decl.flag_code
        self.question = decl.question
        self.version = decl.version
        self._params = decl.params

    def _candidates(self, finding: dict[str, Any]) -> list[str]:
        quotes = [
            str(s.get("quote") or "").strip()
            for s in (finding.get("_evidence_spans") or [])
            if isinstance(s, dict)
        ]
        quotes = [q for q in quotes if q]
        term_regex = self._params.get("term_regex")
        if not term_regex:
            return quotes
        out: list[str] = []
        for q in quotes:
            try:
                out.extend(m if isinstance(m, str) else next((g for g in m if g), "")
                           for m in re.findall(term_regex, q, flags=re.IGNORECASE))
            except re.error:
                return []  # a malformed pinned regex → no candidates → the finding stands
        return [t for t in out if t]

    @staticmethod
    def _resolve_code(client: Any, term: str, search_call: str) -> Any:
        hits = client.call_tool(search_call, {"query": term, "max_hits": 1})
        if isinstance(hits, list) and hits and isinstance(hits[0], dict):
            return hits[0].get("conceptId") or hits[0].get("id")
        return None

    def check(self, finding: dict[str, Any], case: dict[str, Any]) -> Verdict:
        # O2: the edition holder is written by the tool session's ``finally`` (after every
        # verdict-determining call), so the lookup can NEVER perturb the grounding itself;
        # a path that never opens a session honestly stays "unrecorded".
        edition = ["unrecorded"]
        verdict = self._span_grounding(finding, case, edition)
        return replace(verdict, terminology_edition=edition[0])

    def _span_grounding(
        self, finding: dict[str, Any], case: dict[str, Any], edition: list[str]
    ) -> Verdict:
        from lithrim_bench.harness import plugins

        p = self._params
        tool_id = p.get("tool")
        record_path = p.get("record_path")
        if not tool_id or not record_path:
            return Verdict(disproved=False, reason="terminology_subsumption: missing tool/record_path")
        candidates = self._candidates(finding)
        if not candidates:
            return Verdict(
                disproved=False,
                reason="no flagged evidence span to ground (span-level binding); the finding stands",
            )
        record_terms = [str(t) for t in (_resolve_path(case, record_path) or []) if t]
        if not record_terms:
            return Verdict(
                disproved=False,
                reason=f"no record terms at '{record_path}'; nothing to ground against",
            )
        manifest = plugins.resolve_tool(tool_id)
        service = (manifest.service if manifest else None) or {}
        mcp = service.get("mcp") or {}
        if not mcp.get("command"):
            return Verdict(
                disproved=False,
                reason=f"terminology tool {tool_id!r} not available; the finding stands",
            )
        from lithrim_bench.verification.mcp_client import McpStdioClient

        search_call = p.get("search_call") or "search"
        subsumes_call = p.get("subsumes_call") or "subsumed_by"
        edition_op = p.get("edition_op") or service.get("edition_op") or mcp.get("edition_op")
        client = McpStdioClient(command=mcp.get("command"), args=mcp.get("args", []))
        try:
            record_codes = [
                c for c in (self._resolve_code(client, t, search_call) for t in record_terms)
                if c is not None
            ]
            if not record_codes:
                return Verdict(
                    disproved=False, reason="no record term resolved to a concept; the finding stands"
                )
            grounded: list[tuple[str, Any]] = []
            for term in candidates:
                code = self._resolve_code(client, term, search_call)
                if code is None:
                    return Verdict(
                        disproved=False,
                        reason=f"flagged term {term!r} did not resolve; never cleared by silence",
                    )
                if code in record_codes:
                    grounded.append((term, code))
                    continue
                subsumed = any(
                    isinstance(r := client.call_tool(
                        subsumes_call, {"concept_id": code, "subsumer_id": rc}
                    ), dict) and r.get("subsumedBy")
                    for rc in record_codes
                )
                if not subsumed:
                    return Verdict(
                        disproved=False,
                        reason=f"flagged term {term!r} (concept {code}) is not ==/subsumed-by any "
                        f"record concept; the finding stands",
                    )
                grounded.append((term, code))
        except Exception as exc:  # noqa: BLE001 — unreachable tool: the finding stands, never a 500
            return Verdict(
                disproved=False,
                reason=f"terminology tool unreachable ({exc}); the finding stands",
            )
        finally:
            edition[0] = _terminology_edition(client, edition_op)
            with contextlib.suppress(Exception):
                client.close()

        detail = ", ".join(f"{t!r}->{c}" for t, c in grounded)
        return Verdict(
            disproved=True,
            evidence=f"every flagged term is ==/subsumed-by a record concept: {detail} "
            f"(record codes {record_codes})",
            reason="code-grounded by is-a subsumption via the connected terminology tool",
        )


def _norm(s: str) -> str:
    """Lowercase, strip non-alnum-space, collapse whitespace — the term-match normalizer."""
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", str(s).lower()).split())


def _semantic_tag(fsn: str | None) -> str | None:
    """The SNOMED semantic tag = the trailing parenthetical of the FSN, e.g. ``(disorder)`` /
    ``(finding)`` / ``(situation)`` / ``(procedure)``. ``None`` if the FSN has no trailing tag."""
    if not fsn:
        return None
    m = re.search(r"\(([^()]+)\)\s*$", str(fsn))
    return m.group(1).strip().lower() if m else None


def _term_of(result: Any) -> str | None:
    """``result.get("term")`` if the result is a dict, else the result itself (a bare string)."""
    if isinstance(result, dict):
        term = result.get("term")
        return str(term) if term else None
    return str(result) if result else None


class SnomedBatteryGrounding(VerificationContract):
    """FLOOR-BATTERY-1: the ORDERED terminology-battery suppress executor — a live-validated
    note-vs-record diagnosis check (checks 1-3 + 7) over a SNOMED MCP tool (Hermes), resolved and
    opened EXACTLY the way :class:`McpCallGrounding` resolves a tool and builds its
    :class:`McpStdioClient`. It CLEARS a raised finding (``disproved=True``) ONLY on positive
    terminology evidence; on anything short of that the finding STANDS.

    The battery, applied in order to ``{record_code, record_term, note_code, note_term}`` (shaped
    from the case via the same pinned-JUTE mechanism ``McpCallGrounding`` uses — a drifted transform
    REFUSES, the finding stands):

      1. VALIDITY  — both the note and record codes exist. ``concept`` RAISES :class:`McpError` on a
                     non-existent id (not ``None``), so we branch on the exception; a missing code
                     leaves the finding standing.
      2. MISLABEL  — the ``note_term`` must match SOME description (synonym) of ``note_code``, not
                     just the FSN. A term matching no synonym means the code is mislabeled → stands.
      3. CATEGORY  — the note and record FSN semantic tags (``(disorder)`` etc.) must match; a
                     disorder-vs-procedure mismatch → stands.
      7. IS-A DIRECTION — the SUPPORTED generalization is ``record is-a note`` (the record concept
                     is subsumed-by the note concept): SUPPRESS. The reverse (``note`` strict
                     descendant of ``record``) is an UPCODE and is NEVER cleared. No is-a either
                     direction DEFERS (advisory relatedness; the finding stands).

    The three asymmetries hold by construction: never clear an upcode (only the ``record is-a note``
    branch suppresses), never clear without a positive ``subsumedBy`` / valid+labeled result, and
    DEFER on any error/absence.

    Graceful-absent (non-negotiable, mirroring :class:`McpCallGrounding`): an unresolvable tool, a
    tool with no stdio transport, an unreachable server, any ``McpError`` OUTSIDE check 1's validity
    branch, or a shape that will not produce the 4 fields → ``disproved=False`` (the finding STANDS),
    no 500, never a silent clear. This executor is ADDITIVE: it does not touch the frozen council
    seam or :class:`McpCallGrounding`.

    params = {"tool": "<terminology tool id, e.g. hermes_snomed>",   # required
              "arguments_jute": "<pinned JUTE shaping the 4 fields>",
              "arguments_jute_sha256": "<pin hash — refuse on drift>",
              "arguments": {record_code, record_term, note_code, note_term}}  # static fallback
    """

    contract_type = "snomed_battery"

    def __init__(self, decl: VerificationContractDecl, *, http_client: Any | None = None) -> None:
        self.flag_code = decl.flag_code
        self.question = decl.question
        self.version = decl.version
        self._params = decl.params

    def check(self, finding: dict[str, Any], case: dict[str, Any]) -> Verdict:
        from lithrim_bench.harness import plugins

        p = self._params
        tool_id = p.get("tool")
        if not tool_id:
            return Verdict(disproved=False, reason="snomed_battery: missing tool (inconclusive)")
        manifest = plugins.resolve_tool(tool_id)
        if manifest is None:
            return Verdict(
                disproved=False,
                reason=f"snomed_battery: tool {tool_id!r} not available (not_applicable; finding stands)",
            )
        mcp = (manifest.service or {}).get("mcp") or {}
        if not mcp.get("command"):
            return Verdict(
                disproved=False,
                reason=f"snomed_battery: tool {tool_id!r} has no stdio MCP transport yet (not_applicable)",
            )
        # Shape the 4 battery fields via the pinned JUTE (or the static dict) — a drifted transform
        # or an absent shape REFUSES: never grade through it, the finding stands.
        shape = self._shape_arguments(case, finding)
        if not isinstance(shape, dict):
            return Verdict(
                disproved=False,
                reason=(
                    "snomed_battery: arguments_jute hash mismatch or absent shape "
                    "(pinned transform drifted or produced no object); refusing to grade — finding stands"
                ),
            )
        rec_code, rec_term = shape.get("record_code"), shape.get("record_term")
        note_code, note_term = shape.get("note_code"), shape.get("note_term")
        if rec_code in (None, "") or note_code in (None, ""):
            return Verdict(
                disproved=False,
                reason="snomed_battery: shape did not yield record_code/note_code; finding stands",
            )

        from lithrim_bench.verification.mcp_client import McpError, McpStdioClient

        client = McpStdioClient(command=mcp.get("command"), args=mcp.get("args", []))
        try:
            decision, reason = self._battery(
                client, McpError, rec_code, rec_term, note_code, note_term
            )
        except McpError as exc:  # an McpError outside check 1: finding stands, never a 500 or a clear
            return Verdict(
                disproved=False,
                reason=f"snomed_battery: {tool_id} tool error ({exc}); finding stands",
            )
        except Exception as exc:  # noqa: BLE001 — unreachable server: finding stands, never a 500
            return Verdict(
                disproved=False,
                reason=f"snomed_battery: {tool_id} unreachable ({exc}); finding stands",
            )
        finally:
            with contextlib.suppress(Exception):
                client.close()

        return Verdict(disproved=(decision == "SUPPRESS"), reason=reason)

    def _battery(
        self,
        client: Any,
        mcp_error: type[BaseException],
        rec_code: Any,
        rec_term: Any,
        note_code: Any,
        note_term: Any,
    ) -> tuple[str, str]:
        """The ordered check 1-3 + 7 battery. Returns ``(decision, reason)`` where decision is one
        of ``SUPPRESS`` (clear), ``STAND`` (positive disproof of a clear), or ``DEFER`` (advisory,
        not cleared). An ``McpError`` raised OUTSIDE check 1's validity branch propagates (the caller
        maps it to a graceful non-clear)."""
        rc, nc = int(rec_code), int(note_code)

        # check 1 VALIDITY: concept() RAISES McpError on a non-existent id -> branch on the exception.
        for who, cid in (("note", nc), ("record", rc)):
            try:
                client.call_tool("concept", {"concept_id": cid})
            except mcp_error:
                return ("STAND", f"check1 validity: {who} code {cid} does not exist")

        # check 2 MISLABEL: note_term must match SOME description (synonym) of note_code, not just FSN.
        fsn = _term_of(client.call_tool("fully_specified_name", {"concept_id": nc}))
        descs = client.call_tool("descriptions", {"concept_id": nc}) or []
        terms = [d.get("term") for d in descs if isinstance(d, dict)]
        terms.append(fsn)
        if note_term and not any(
            set(_norm(note_term).split()).issubset(set(_norm(t).split())) for t in terms if t
        ):
            return (
                "STAND",
                f"check2 mislabel: code {nc} ({fsn}) has no synonym matching note '{note_term}'",
            )

        # check 3 CATEGORY: the FSN semantic tags of note vs record must match.
        rf = _term_of(client.call_tool("fully_specified_name", {"concept_id": rc}))
        note_tag, rec_tag = _semantic_tag(fsn), _semantic_tag(rf)
        if note_tag and rec_tag and note_tag != rec_tag:
            return ("STAND", f"check3 category: note({note_tag}) != record({rec_tag})")

        # check 7 IS-A DIRECTION: clear ONLY on the supported ``record is-a note`` generalization.
        if (client.call_tool("subsumed_by", {"concept_id": rc, "subsumer_id": nc}) or {}).get(
            "subsumedBy"
        ):
            return ("SUPPRESS", "check7: record is-a note (supported generalization)")
        if (client.call_tool("subsumed_by", {"concept_id": nc, "subsumer_id": rc}) or {}).get(
            "subsumedBy"
        ):
            return ("STAND", "check7: note strict-descendant of record (upcode)")
        return ("DEFER", "check7: no is-a either direction (advisory relatedness/synonym; not cleared)")

    def _shape_arguments(self, case: dict[str, Any], finding: dict[str, Any]) -> dict | None:
        """The battery-field source, mirroring :meth:`McpCallGrounding._shape_arguments`:

        - No ``arguments_jute`` -> ``params.get("arguments") or {}`` (the static path).
        - ``arguments_jute`` present -> HASH-VERIFY against ``arguments_jute_sha256`` FIRST; on
          mismatch return ``None`` (REFUSE — never grade through a drifted transform). On match,
          apply the pinned JUTE to ``{case, finding}`` in-memory via the same :3031 ``test_template``
          seam and return the shaped object; a broken/absent shape returns ``None`` so the finding
          stands rather than grade through it.
        """
        p = self._params
        jute = p.get("arguments_jute")
        if not jute:
            return p.get("arguments") or {}
        want = p.get("arguments_jute_sha256")
        if not want or hashlib.sha256(jute.encode("utf-8")).hexdigest() != want:
            return None  # drift: refuse, finding stands
        try:
            applied = _jute_client().test_template(jute, {"case": case, "finding": finding})
        except Exception:  # noqa: BLE001 — a dead :3031 must not grade through; finding stands
            return None
        if not isinstance(applied, dict) or applied.get("compiled") is False:
            return None
        output = applied.get("output")
        return output if isinstance(output, dict) else None


# contract_type -> executor factory. This is the core-GENERIC SUPPRESS registry
# (per-finding contracts that disprove an existing confident-but-wrong finding). The
# structural FLOOR direction (artifact-level contracts that inject a BLOCK the council
# missed) is a categorically different shape — it is keyed by ``floor_contract_types()``
# and run by ``_run_floor``, not here.
#
# ``kb_grounding`` (WS-7b) is the KB-grounded suppress executor — the S-BS-7
# presence-check generalized to the backend KB. It needs the injected ``http_client``
# (it composes over live :8002), so ``_build_contract`` threads it in; ``PresenceCheck``
# is pure-stdlib and ignores it.
#
# PACK-3: the CLINICAL suppress executor (``record_presence`` / GROUND-FLOOR-1) relocated
# OUT of the core into the active pack (``packs/healthcare/floors.py``). The full suppress
# registry the engine runs — and that the withstands-gate reads — is ``suppress_executors()``
# = this generic dict MERGED with the pack's ``SUPPRESS_EXECUTORS`` (lazy + cached, so the
# pack is loaded only on first grounding use and the dependency points pack→core, no cycle).
_CONTRACT_EXECUTORS = {
    "presence_check": PresenceCheck,
    "kb_grounding": KbGrounding,
    # CONN-WEBSEARCH-1: non-authoritative by construction — it attaches web evidence but its
    # ``check`` ALWAYS returns ``disproved=False``, so it can never suppress (clear) a finding.
    "web_search": WebSearchGrounding,
    # GROUND-FLOOR-SOURCE-1: the answer⊆source faithfulness floor — pure-stdlib/in_process, the
    # S-BS-7 presence-check generalized (suppress-only-on-FULL-grounding, anti-masking).
    "source_grounding": SourceGrounding,
    # LAYER2-SUPPRESS-1: the evidence-integrity gate — a finding whose own evidence spans are
    # verbatim source text refutes itself. Pure-stdlib/in_process, span-level, corpus-gated per code.
    "evidence_presence": EvidencePresence,
    # TOOL-AUTHOR-1: the generic authored-MCP-tool executor (advisory/corroborated; builds its own
    # McpStdioClient via resolve_tool, so it is NOT in _HTTP_CONTRACT_TYPES).
    "mcp_call": McpCallGrounding,
    # REPRO-1 R4c: the core-generic terminology-subsumption suppress executor — span-driven,
    # tool-driven (a ToolBuilder-authored terminology server), zero domain strings in core.
    "terminology_subsumption": TerminologySubsumption,
    # FLOOR-BATTERY-1: the ordered terminology battery (validity/mislabel/category/is-a) over a
    # SNOMED MCP tool — clears a note-vs-record diagnosis ONLY on the supported ``record is-a note``
    # generalization; never clears an upcode, a bad/mislabeled code, or a category mismatch.
    "snomed_battery": SnomedBatteryGrounding,
}
_HTTP_CONTRACT_TYPES = {"kb_grounding", "web_search"}


@dataclass(frozen=True)
class FloorExecutor:
    """One structural-floor executor: how to build its tool + its pinned reference.

    ``tool_factory(http_client) -> VerificationTool`` (the injected client threads to the
    HTTP-composing tools; pure-stdlib tools ignore it). ``reference_builder(params) -> dict``
    lifts the SME-pinned reference out of the ontology declaration's ``params``. The
    generic dispatch (artifact guard, ``Claim``/``VerificationSpec`` construction,
    ``tool.verify``) stays in :func:`_run_floor`; the registry supplies only these two."""

    tool_factory: Any
    reference_builder: Any


@lru_cache(maxsize=1)
def _core_floor_executors() -> dict[str, FloorExecutor]:
    """The core-GENERIC floor executors (``structural_jute`` / ``jute_gen`` / ``value_presence``).
    Lazy so this module's own import stays stdlib-only — importing the ``verification`` tools
    (httpx/dspy lazy within them) is deferred to the first floor run. The CLINICAL floor
    (``dosage_grounding``) is registered by the pack, not here (PACK-3). CORE-FLOOR-1: ``value_presence``
    is a domain-agnostic completeness floor, so it lives in core (available to EVERY pack incl.
    healthcare), not pack-local to narrative."""
    from lithrim_bench.verification import (
        FactPreservationTool,
        JuteGenValidatorTool,
        SpeakerAttributionTool,
        StructuralJuteTool,
        ValuePresenceTool,
    )

    def _value_presence_ref(params: dict[str, Any]) -> dict[str, Any]:
        ref: dict[str, Any] = {"value_regex": params["value_regex"]}
        if params.get("source_path"):
            ref["source_path"] = params["source_path"]
        if params.get("match"):
            ref["match"] = params["match"]
        return ref

    def _structural_jute_ref(params: dict[str, Any]) -> dict[str, Any]:
        ref = {
            "service": params["service"],
            "mapping_selector": params["mapping_selector"],
            "artifact_kind": params["artifact_kind"],
        }
        if params.get("pinned_content_sha256"):
            ref["pinned_content_sha256"] = params["pinned_content_sha256"]
        return ref

    def _jute_gen_ref(params: dict[str, Any]) -> dict[str, Any]:
        ref = {
            "service": params["service"],
            "artifact_kind": params["artifact_kind"],
            "pinned_template": params["pinned_template"],
        }
        if params.get("pinned_template_sha256"):
            ref["pinned_template_sha256"] = params["pinned_template_sha256"]
        return ref

    # REPRO-1 R4a/R4b: the bounded-extraction floors' reference = the SME-pinned prose + the
    # extraction knobs (all UI data). The LM rides the provider seam lazily inside the tool.
    def _extraction_ref(required_key: str):
        def _build(params: dict[str, Any]) -> dict[str, Any]:
            ref: dict[str, Any] = {required_key: params[required_key]}
            for opt in ("k", "source_path", "extractor_role"):
                if params.get(opt):
                    ref[opt] = params[opt]
            return ref

        return _build

    return {
        "structural_jute": FloorExecutor(
            tool_factory=lambda http_client: StructuralJuteTool(http_client=http_client),
            reference_builder=_structural_jute_ref,
        ),
        "jute_gen": FloorExecutor(
            tool_factory=lambda http_client: JuteGenValidatorTool(http_client=http_client),
            reference_builder=_jute_gen_ref,
        ),
        "value_presence": FloorExecutor(
            tool_factory=lambda http_client: ValuePresenceTool(),
            reference_builder=_value_presence_ref,
        ),
        "fact_preservation": FloorExecutor(
            tool_factory=lambda http_client: FactPreservationTool(),
            reference_builder=_extraction_ref("fact"),
        ),
        "speaker_attribution": FloorExecutor(
            tool_factory=lambda http_client: SpeakerAttributionTool(),
            reference_builder=_extraction_ref("statement"),
        ),
    }


@lru_cache(maxsize=8)
def _pack_registries(pack: str) -> tuple[dict[str, Any], dict[str, FloorExecutor]]:
    """The active pack's ``(SUPPRESS_EXECUTORS, FLOOR_EXECUTORS)`` registration dicts, or
    ``({}, {})`` when the pack declares no ``floors`` module. Cached per pack id."""
    from . import pack as _pack

    module = _pack.load_pack_floors(pack)
    if module is None:
        return {}, {}
    return (
        dict(getattr(module, "SUPPRESS_EXECUTORS", {})),
        dict(getattr(module, "FLOOR_EXECUTORS", {})),
    )


def _active_pack() -> str:
    from . import pack as _pack

    return _pack.active_pack()


def suppress_executors(pack: str | None = None) -> dict[str, Any]:
    """The full suppress registry the engine runs: the core-generic executors MERGED with
    the active pack's ``SUPPRESS_EXECUTORS``. The withstands-gate
    (``runtime/council/signals.py``) reads THIS — so a pack-registered suppress executor
    (e.g. the clinical ``record_presence``) is moat-visible, not just visible to ``ground()``.

    FAUTH-2a: ``pack`` is OPTIONAL and defaults to ``_active_pack()`` — the no-arg call (the
    withstands-gate + ``ground()`` at grade time, in the correct-pack subprocess) is byte-behavior
    identical. An explicit ``pack`` lets the BFF author-time gate resolve the active WORKSPACE's
    grade pack (≠ the BFF process pack); see ``apps/bff/app.py`` ``_active_lens_by_role``."""
    suppress, _ = _pack_registries(pack or _active_pack())
    return {**_CONTRACT_EXECUTORS, **suppress}


def floor_executors(pack: str | None = None) -> dict[str, FloorExecutor]:
    """The full floor registry: the core-generic floors MERGED with the active pack's
    ``FLOOR_EXECUTORS`` (e.g. the clinical ``dosage_grounding``). FAUTH-2a: ``pack`` is OPTIONAL
    and defaults to ``_active_pack()`` (no-arg behavior unchanged)."""
    _, floors = _pack_registries(pack or _active_pack())
    return {**_core_floor_executors(), **floors}


def floor_contract_types(pack: str | None = None) -> set[str]:
    """The set of contract_types the floor dispatch knows (core ∪ pack). FAUTH-2a: optional
    ``pack`` defaults to ``_active_pack()`` (no-arg behavior unchanged)."""
    return set(floor_executors(pack))


# Contracts that compose over an out-of-process service (the manifest ``transport`` field):
# the kb_grounding suppress executor (over :8002) + the JUTE structural floors (over :3031).
# Everything else — presence_check + the pack's pure-stdlib executors — is ``in_process``.
_SERVICE_CONTRACT_TYPES = _HTTP_CONTRACT_TYPES | {"structural_jute", "jute_gen"}


def _contract_transport(contract_type: str, extra_service_types: frozenset[str] = frozenset()) -> str:
    return "service" if contract_type in (_SERVICE_CONTRACT_TYPES | extra_service_types) else "in_process"


@lru_cache(maxsize=8)
def _pack_service_contract_types(pack: str) -> frozenset[str]:
    """The active pack's declared service-transport contract_types — its ``floors`` module's
    optional ``SERVICE_CONTRACT_TYPES`` (default empty). So a pack that ships a service-transport
    floor (one that composes over an out-of-process service) is declared ``transport=service``
    in :func:`contract_plugins`, not the core default ``in_process`` (S-BS-133). No pack declares
    any today → behavior-identical now; this is the forward-looking hook the manifest ``transport``
    field + provenance need. The field is **declarative metadata** — dispatch is unchanged (gated
    by ``_HTTP_CONTRACT_TYPES``, not this)."""
    from . import pack as _pack

    module = _pack.load_pack_floors(pack)
    if module is None:
        return frozenset()
    return frozenset(getattr(module, "SERVICE_CONTRACT_TYPES", ()) or ())


def contract_plugins() -> list[Any]:
    """Declare the contract registry (core ∪ the active pack) as ``kind: contract`` plugins — the
    Plugin Phase-1 declaration layer over the EXISTING merge (D3).

    **Behavior-identical:** this ENUMERATES :func:`suppress_executors` / :func:`floor_executors`;
    it does NOT change dispatch (``_build_contract`` / ``_run_floor`` / the moat-visible
    ``suppress_executors()`` read in ``runtime/council/signals.py`` are untouched). The pack-floors
    fold already made the merge open/closed (a pack ships executors via its ``floors`` module with
    zero engine edits); this adds the declared ``kind/tier/transport`` over it. Core executors are
    ``tier: core``; pack-contributed executors inherit the active pack's tier (so healthcare's
    clinical ``record_presence`` / ``dosage_grounding`` are ``tier: pro``). ``PluginManifest`` +
    ``pack`` are imported lazily so ``import grounding`` keeps its existing import surface."""
    from lithrim_bench.harness import pack as _pack
    from lithrim_bench.harness.plugins import PluginManifest

    active = _active_pack()
    pack_tier = _pack._manifest(active).get("tier", "core")
    pack_suppress, pack_floors = _pack_registries(active)
    pack_service = _pack_service_contract_types(active)  # S-BS-133: pack-declared service transports

    out: list[PluginManifest] = []
    for ctype in _CONTRACT_EXECUTORS:
        out.append(
            PluginManifest(
                id=ctype,
                kind="contract",
                tier="core",
                transport=_contract_transport(ctype),
                implements="grounding.suppress",
                contract_types=[ctype],
            )
        )
    for ctype in _core_floor_executors():
        out.append(
            PluginManifest(
                id=ctype,
                kind="contract",
                tier="core",
                transport=_contract_transport(ctype),
                implements="grounding.floor",
                contract_types=[ctype],
            )
        )
    for ctype in pack_suppress:
        out.append(
            PluginManifest(
                id=ctype,
                kind="contract",
                tier=pack_tier,
                transport=_contract_transport(ctype, pack_service),
                implements="grounding.suppress",
                contract_types=[ctype],
            )
        )
    for ctype in pack_floors:
        out.append(
            PluginManifest(
                id=ctype,
                kind="contract",
                tier=pack_tier,
                transport=_contract_transport(ctype, pack_service),
                implements="grounding.floor",
                contract_types=[ctype],
            )
        )
    return out


def _build_contract(
    decl: VerificationContractDecl, *, http_client: Any | None = None
) -> VerificationContract:
    factory = suppress_executors().get(decl.contract_type)
    if factory is None:
        raise ValueError(f"no executor registered for contract_type {decl.contract_type!r}")
    # HTTP-composing suppress executors (kb_grounding) reuse the injected client;
    # pure-stdlib ones (presence_check / the pack's record_presence) take only the declaration.
    if decl.contract_type in _HTTP_CONTRACT_TYPES:
        return factory(decl, http_client=http_client)
    return factory(decl)


def validate_contract_params(decl: VerificationContractDecl, pack: str | None = None) -> None:
    """Author-time guard (GRADE-GUARD-1): DRY-CONSTRUCT ``decl``'s contract to validate its params
    shape, raising ``ValueError`` on malformed params. The FAUTH-2 author-time gate calls this so a
    contract with bad params (e.g. a ``presence_check`` authored with the inert default, no
    ``med_source``) is rejected (422) BEFORE it is persisted — instead of detonating ``ground()``
    with a cryptic ``KeyError`` at grade time. READ-ONLY: it constructs the suppress executor, or the
    floor's reference + ``VerificationSpec`` (which validates the required reference keys), and
    discards the result; it never grades and never touches a service.

    ``pack`` resolves the registry for the ACTIVE WORKSPACE'S grade pack (the FAUTH-2a family): a
    pack-registered type (e.g. the clinical ``record_presence``) is unknown to the BFF process pack
    (``_core``), so the gate passes the workspace pack — else it false-rejects the pack's executors.
    ``None`` defaults to the process pack (byte-behavior for the in-pack callers)."""
    ct = decl.contract_type
    suppress = suppress_executors(pack)
    floor = floor_executors(pack)
    try:
        if ct in suppress:
            factory = suppress[ct]
            # mirror _build_contract's dispatch (HTTP-composing executors take the client)
            factory(decl, http_client=None) if ct in _HTTP_CONTRACT_TYPES else factory(decl)
        elif ct in floor:
            from lithrim_bench.verification import VerificationSpec

            reference = floor[ct].reference_builder(decl.params)
            VerificationSpec(  # validates the required reference keys (raises on missing)
                tool=ct,
                applies_to_flags=(decl.flag_code,),
                locus=decl.params.get("locus", ""),
                reference=reference,
                version=decl.version,
            )
        else:
            raise ValueError(f"no executor registered for contract_type {ct!r}")
    except Exception as exc:  # noqa: BLE001 - normalize any construction error to a clear ValueError
        raise ValueError(
            f"malformed contract for {ct!r}: {type(exc).__name__}: {exc}"
        ) from exc


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

    from lithrim_bench.verification import STRUCTURAL_CONFORMANCE, Claim, VerificationSpec

    executor = floor_executors().get(decl.contract_type)
    if executor is None:  # pragma: no cover - guarded by the partition in ground()
        raise ValueError(f"no floor executor for contract_type {decl.contract_type!r}")

    params = decl.params
    locus = params.get("locus", "")
    tool = executor.tool_factory(http_client)
    reference = executor.reference_builder(params)

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


def _classify_coverage(
    active: list[dict[str, Any]],
    suppressed: list[dict[str, Any]],
    skipped_non_gradeable: list[dict[str, Any]],
    suppress_codes: set[str],
    verdict: str,
) -> dict[str, Any]:
    """FLOOR-COVERAGE-1 — label every surviving finding by what backed it, read-only.

    Each ACTIVE finding falls in exactly one bucket:
      - ``grounded``   — a structural floor injected it (``_floor``): deterministic block support.
      - ``declined``   — a bound contract ran but errored/could-not-decide (``_grounding_error``).
      - ``unrefuted``  — a suppress contract EXISTS for the code, ran, and did not clear it: the
                         finding stands as a judge assertion the floor examined but could not refute.
      - ``judge_only`` — a coded finding with NO deterministic contract covering it: the pure-judge,
                         no-backstop case (the F10-shaped residual reproduced live).
      - ``null``       — a null-code finding (S-BS-8).
    ``suppressed`` findings are ``cleared``; ``skipped_non_gradeable`` are ``reference``.

    ``floor_backstopped`` answers "does the deterministic floor materially support THIS verdict":
    a BLOCK is backstopped iff a finding is ``grounded``; a PASS iff a finding was ``cleared``.
    A BLOCK resting solely on ``judge_only``/``unrefuted`` findings is NOT backstopped — the exact
    false-BLOCK the honesty moat was previously silent about.
    """
    counts = {
        "grounded": 0,
        "cleared": 0,
        "declined": 0,
        "unrefuted": 0,
        "judge_only": 0,
        "reference": 0,
        "null": 0,
    }
    per_finding: list[dict[str, Any]] = []
    for f in active:
        code = f.get("code")
        if code is None:
            tag = "null"
        elif f.get("_floor"):
            tag = "grounded"
        elif "_grounding_error" in f:
            tag = "declined"
        elif code in suppress_codes:
            tag = "unrefuted"
        else:
            tag = "judge_only"
        counts[tag] += 1
        per_finding.append({"code": code, "coverage": tag})
    for s in suppressed:
        counts["cleared"] += 1
        per_finding.append({"code": s["finding"].get("code"), "coverage": "cleared"})
    for r in skipped_non_gradeable:
        counts["reference"] += 1
        per_finding.append({"code": r.get("code"), "coverage": "reference"})

    if verdict == "BLOCK":
        backstopped = counts["grounded"] > 0
    elif verdict == "PASS":
        backstopped = counts["cleared"] > 0
    else:
        backstopped = counts["grounded"] > 0 or counts["cleared"] > 0

    return {**counts, "floor_backstopped": backstopped, "per_finding": per_finding}


def rescore_without_floor(
    active: list[dict[str, Any]],
    suppressed: list[dict[str, Any]],
    severity_map: Any,
) -> str:
    """READ-ATTRIB-1: the verdict this grade would carry had the floor plane never run.

    Drop what a floor contract INJECTED (``_floor``) and restore what a suppress contract
    CLEARED, then apply the SAME ``rescore`` the live verdict uses. Comparing the live verdict
    against a verdict produced by a different rule (the council's tier verdict) attributes rule
    disagreement to the floor; comparing it against this attributes only the floor to the floor.

    Pure and read-only: the caller's ``active``/``suppressed`` are never mutated.
    """
    counterfactual = [f for f in active if not f.get("_floor")]
    counterfactual += [s.get("finding") or {} for s in suppressed]
    return severity_map.rescore(counterfactual)


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
    declared in the ontology (``contract_type`` in ``floor_contract_types()``) runs
    over the *artifact*. A real structural violation the council missed
    (``conforms is False``) injects a BLOCK-driving finding into ``active`` so the
    re-score flips PASS→BLOCK. ``http_client`` is injectable for the floor's apply
    (a fake/replay client offline; ``None`` => the live ``:3031`` path). When the
    ontology declares NO floor contract — the committed clinical default — the floor
    pass is a no-op and the result is identical to the pre-WS-3 ``ground()`` (with
    ``floor_blocks == []``).
    """
    ontology = ontology or load_ontology()
    suppress_registry = suppress_executors()
    floor_types = floor_contract_types()
    suppress_decls = [d for d in ontology.contracts if d.contract_type in suppress_registry]
    floor_decls = [d for d in ontology.contracts if d.contract_type in floor_types]
    unknown = [
        d
        for d in ontology.contracts
        if d.contract_type not in suppress_registry and d.contract_type not in floor_types
    ]
    if unknown:
        raise ValueError(f"no executor registered for contract_type {unknown[0].contract_type!r}")
    # GRADE-GUARD-1: a contract with malformed params (e.g. a presence_check authored with the inert
    # default, no med_source) must NOT crash the whole grade at construction. SKIP-LOG it (surfaced,
    # never silent) — the same "never silently drop, never abort the grade" discipline as the S-BS-8/10
    # skip-logging. The author-time gate (validate_contract_params) is the prevention; this is defense.
    # LAYER2-SUPPRESS-1: a flag_code may declare a CHAIN of suppress contracts, run in
    # declaration order, first disprove wins. (The pre-consensus withstands gate still
    # challenges with the FIRST declared contract only — signals.py binds via the frozen
    # ``contract_for`` read; the full chain is a ground()-side authority.)
    contracts: dict[str, list[VerificationContract]] = {}
    skipped_malformed: list[dict[str, Any]] = []
    for decl in suppress_decls:
        try:
            contracts.setdefault(decl.flag_code, []).append(
                _build_contract(decl, http_client=http_client)
            )
        except Exception as exc:  # noqa: BLE001 - a malformed contract must degrade, not crash
            skipped_malformed.append(
                {"decl": decl, "stage": "build", "error": f"{type(exc).__name__}: {exc}"}
            )
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
        chain = contracts.get(code)
        if not chain:
            active.append(finding)
            continue
        enriched = dict(finding)
        ev = semantic_evidence.get(code)
        if ev is not None:
            enriched["_evidence_spans"] = ev.get("spans")
        disproving_verdict = None
        disproving_contract = None
        first_error: str | None = None
        for contract in chain:
            try:
                verdict = contract.check(enriched, case)
            except Exception as exc:  # noqa: BLE001
                # A service-transport suppress executor (one composing over an out-of-process
                # tool or service) can raise if that service is unreachable. Never clear by
                # silence — but a dead service must not silence the REST of the chain either:
                # record the first error for audit and let the remaining contracts have their
                # say. The pure-stdlib executors never reach this path.
                if first_error is None:
                    first_error = f"{type(exc).__name__}: {exc}"
                continue
            if verdict.disproved:
                disproving_verdict, disproving_contract = verdict, contract
                break
        if disproving_verdict is not None:
            suppressed.append(
                {
                    "finding": finding,
                    "verdict": disproving_verdict,
                    "contract": disproving_contract,
                }
            )
        elif first_error is not None:
            active.append({**finding, "_grounding_error": first_error})
        else:
            active.append(finding)

    # WS-3 structural floor (the inverse direction): inject a BLOCK the council missed.
    floor_blocks: list[dict[str, Any]] = []
    for decl in floor_decls:
        # GRADE-GUARD-1: a malformed floor contract (missing inject_flag_code/severity, a bad
        # reference, or an unreachable service) must SKIP-LOG, not crash the grade. A floor that
        # cannot run injects NOTHING (the conservative "never fabricate a block on uncertainty"
        # posture, == the conforms=None branch) and is surfaced.
        try:
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
        except Exception as exc:  # noqa: BLE001 - a malformed/unreachable floor must degrade, not crash
            skipped_malformed.append(
                {"decl": decl, "stage": "floor", "error": f"{type(exc).__name__}: {exc}"}
            )

    verdict = ontology.severity_map.rescore(active)
    # READ-ATTRIB-1: the honest floor counterfactual, computed with the SAME rule as ``verdict``
    # so ``verdict`` vs ``verdict_no_floor`` is a PURE floor delta. Without it the scorecard's
    # pre/post band compared two different rules (the council's tier verdict vs this rescore) and
    # billed the whole gap to the floor. Read-only over the finalized buckets, like ``coverage``.
    verdict_no_floor = rescore_without_floor(active, suppressed, ontology.severity_map)
    # FLOOR-COVERAGE-1: derive the coverage provenance READ-ONLY from the finalized buckets —
    # ``active``/``suppressed``/``verdict`` above are untouched (the invariance guard).
    coverage = _classify_coverage(
        active, suppressed, skipped_non_gradeable, set(contracts.keys()), verdict
    )
    return GroundedResult(
        active=active,
        suppressed=suppressed,
        ungrounded=ungrounded,
        skipped_non_gradeable=skipped_non_gradeable,
        floor_blocks=floor_blocks,
        skipped_malformed=skipped_malformed,
        verdict=verdict,
        verdict_no_floor=verdict_no_floor,
        original_verdict=result.get("verdict"),
        weights=dict(ontology.severity_map.weights),
        coverage=coverage,
        result=result,
        case=case,
    )
