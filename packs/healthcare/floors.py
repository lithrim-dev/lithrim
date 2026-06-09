"""Healthcare pack — the clinical grounding EXECUTORS (PACK-3, layer 3).

The domain-agnostic grounding engine (``lithrim_bench/harness/grounding.py`` +
``lithrim_bench/verification/``) supplies the generic machinery — the ``ground()``
orchestrator, the suppress/floor registries, the ``VerificationTool`` base, and the
``StructuralJute``/``KbRag``/``RecordRag`` tools. This module is the FIRST
packs-as-CODE contribution: the *clinical* executors that used to live in the core
relocate here, behind the pack executor-registration interface
(``harness.pack.load_pack_floors``). They are **behavior-identical** to their former
core homes — the move is mechanical (healthcare-realm-as-pack).

The dependency points **pack → core** only (never core → pack at import): this module
imports the core primitives it needs (``VerificationContract``/``Verdict``/
``_artifact_content`` from grounding; ``VerificationTool``/``_norm``/``_dig`` from the
toolbox; ``Claim``/``VerificationSpec``/the name constants from the spec; the
``FloorExecutor`` record from grounding). It is import-clean (pure-stdlib at import;
the relocated executors pull no httpx/dspy/onnx). The core loads it LAZILY on first
grounding use, by which point all core modules are imported — so there is no cycle.

What lives here:
  * ``record_presence`` (GROUND-FLOOR-1) — the SUPPRESS executor :class:`RecordPresence`
    (the S-BS-7 presence-check generalized from the transcript to the patient record),
    wrapping the proven :class:`InRowTool` + ``extract_pmh_items`` + ``snomed_core``.
  * ``dosage_grounding`` — the FLOOR executor :class:`DosageGroundingTool` (the offline
    deterministic dose-faithfulness floor).
The pack exposes them via the two module-level registration dicts at the bottom:
``SUPPRESS_EXECUTORS`` (merged into the core suppress registry) and ``FLOOR_EXECUTORS``
(merged into the core floor registry). The frozen withstands-gate
(``runtime/council/signals.py``) reads the merged suppress registry — so registering
``record_presence`` here wires BOTH gates (post-consensus ``ground()`` and the
pre-consensus withstands-gate), exactly as before.
"""

from __future__ import annotations

import json
import re
from typing import Any

from lithrim_bench.harness.grounding import (
    FloorExecutor,
    Verdict,
    VerificationContract,
    _artifact_content,
)
from lithrim_bench.harness.ontology import VerificationContractDecl
from lithrim_bench.verification.spec import (
    RECORD_PRESENCE,
    TOOL_DOSAGE_GROUNDING,
    Claim,
    VerificationResult,
    VerificationSpec,
)
from lithrim_bench.verification.tools import VerificationTool, _dig, _norm


# --------------------------------------------------------------------------- #
# clinical extraction helpers (relocated from verification/tools.py)
# --------------------------------------------------------------------------- #
def _core(s: Any) -> str:
    # drop a trailing SNOMED-style qualifier: "... (finding)" / "(disorder)" / "(situation)"
    return _norm(re.sub(r"\s*\([^)]*\)\s*$", "", str(s)))


def extract_pmh_items(soap_text: str) -> list[str]:
    items, in_pmh = [], False
    for line in str(soap_text).splitlines():
        st = line.strip()
        if st.upper().startswith("PMH"):
            in_pmh = True
            continue
        if in_pmh:
            if st.startswith("- "):
                items.append(st[2:].strip())
            elif st.endswith(":"):  # next section header
                break
    return list(dict.fromkeys(items))  # dedup, preserve order


_DOSE_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:MG/ML|MG/ACTUAT|MCG|MG|ML|G|UNITS?)\b", re.IGNORECASE)


def _norm_dose(token: str) -> str:
    return re.sub(r"\s+", "", str(token)).upper()


def extract_plan_dose_tokens(soap_text: str) -> list[str]:
    """Dose tokens (e.g. '3000MG', '5 MG') found in the PLAN section of a SOAP note."""
    lines = str(soap_text).splitlines()
    plan = ""
    for i, line in enumerate(lines):
        if line.strip().upper().startswith("PLAN"):
            plan = "\n".join(lines[i + 1 :])
            break
    return _DOSE_RE.findall(plan)


# --------------------------------------------------------------------------- #
# InRowTool — the proven deterministic record-presence primitive
# --------------------------------------------------------------------------- #
class InRowTool(VerificationTool):
    """Structured-oracle presence check against a dotted path in the case row.

    reference = {"oracle_path": "patient_profile.conditions",
                 "extractor": "soap_pmh_items" | "soap_plan_dose_tokens",
                 "match": "snomed_core" | "dose_token"}
    """

    name = "in_row"

    _EXTRACTORS = {
        "soap_pmh_items": extract_pmh_items,
        "soap_plan_dose_tokens": extract_plan_dose_tokens,
    }

    def verify(self, claim: Claim, spec: VerificationSpec) -> VerificationResult:
        ref = spec.reference
        extractor = self._EXTRACTORS.get(ref["extractor"])
        if extractor is None:
            raise ValueError(f"unknown in_row extractor {ref['extractor']!r}")

        subject_items = extractor(claim.subject)
        oracle_items = _dig(claim.source, ref["oracle_path"])
        ungrounded = self._ungrounded(ref["match"], subject_items, oracle_items)

        conforms = len(ungrounded) == 0
        evidence = {
            "oracle_path": ref["oracle_path"],
            "extractor": ref["extractor"],
            "match": ref["match"],
            "items_checked": len(subject_items),
            "oracle_size": len(oracle_items),
            "ungrounded": ungrounded,
        }
        manifest = {
            "tool": self.name,
            "deterministic": True,
            "spec_version": spec.version,
            "locus": spec.locus,
            "oracle_path": ref["oracle_path"],
            "match": ref["match"],
        }
        return VerificationResult(conforms=conforms, evidence=evidence, manifest=manifest)

    @staticmethod
    def _ungrounded(match: str, subject_items: list[str], oracle_items: list) -> list[str]:
        if match == "snomed_core":
            full = {_norm(o) for o in oracle_items}
            cores = {_core(o) for o in oracle_items}
            return [it for it in subject_items if _norm(it) not in full and _core(it) not in cores]
        if match == "dose_token":
            oracle_doses: set[str] = set()
            for o in oracle_items:
                oracle_doses |= {_norm_dose(t) for t in _DOSE_RE.findall(str(o))}
            return [it for it in subject_items if _norm_dose(it) not in oracle_doses]
        raise ValueError(f"unknown in_row match strategy {match!r}")


# --------------------------------------------------------------------------- #
# DosageGroundingTool — deterministic dose-faithfulness floor (offline, no network)
# --------------------------------------------------------------------------- #
class DosageGroundingTool(VerificationTool):
    """Floor: every medication dose DOCUMENTED in the artifact must be grounded in
    the encounter evidence — the transcript instruction and, when present, the
    patient record. A documented dose grounded in NEITHER is a dosage-drift
    violation (``conforms=False``); ``ground()`` then injects WRONG_DOSAGE, flipping
    the verdict independent of any judge — a deterministic floor, not an LLM.

    This is the dose analogue of the record-grounding moat: it grounds against the
    transcript AND the chart, not the transcript alone — closing the same
    transcript-only blind spot that makes a judge flag a record-sourced dose.

    reference = {"dose_regex": <pinned extraction pattern>,            # required, SME-pinned
                 "transcript_path": "transcript",                      # free-text encounter (default)
                 "record_path": "patient_profile.active_medications"}  # optional chart oracle

    Conservative: when the artifact documents no parseable dose, ``conforms=None``
    (inconclusive — never flips a verdict, never clears by silence).
    """

    name = TOOL_DOSAGE_GROUNDING

    def verify(self, claim: Claim, spec: VerificationSpec) -> VerificationResult:
        ref = spec.reference
        dose_re = re.compile(ref["dose_regex"], re.IGNORECASE)

        def _doses(text: Any) -> set[str]:
            return {_norm_dose(m.group(0)) for m in dose_re.finditer(str(text))}

        subject = claim.subject if isinstance(claim.subject, str) else json.dumps(claim.subject)
        documented = _doses(subject)

        transcript_path = ref.get("transcript_path", "transcript")
        grounded = _doses((claim.source or {}).get(transcript_path) or "")
        record_path = ref.get("record_path")
        record_items = _dig(claim.source, record_path) if record_path else []
        for item in record_items:
            grounded |= _doses(item)

        manifest = {
            "tool": self.name,
            "deterministic": True,
            "spec_version": spec.version,
            "locus": spec.locus,
            "transcript_path": transcript_path,
            "record_path": record_path,
        }
        if not documented:
            return VerificationResult(
                conforms=None,
                evidence={"reason": "artifact documents no parseable dose", "documented_doses": []},
                manifest=manifest,
            )

        ungrounded = sorted(documented - grounded)
        evidence = {
            "documented_doses": sorted(documented),
            "grounded_doses": sorted(grounded),
            "ungrounded_doses": ungrounded,
            "grounded_against": ["transcript"] + (["record"] if record_items else []),
        }
        return VerificationResult(conforms=not ungrounded, evidence=evidence, manifest=manifest)


# --------------------------------------------------------------------------- #
# _decode_artifact_soap — the SOAP body inside a FHIR DocumentReference artifact
# --------------------------------------------------------------------------- #
def _decode_artifact_soap(case: dict[str, Any]) -> str | None:
    """The SOAP note inside the first artifact's FHIR DocumentReference, or ``None``.

    The corpus artifact is a DocumentReference JSON string with the SOAP body at
    ``content[0].attachment.data`` stored as **plaintext** — the injector reads and
    writes it as a string with no base64 (``injectors/_soap.py``). Real-FHIR base64
    attachments are FHIR-1, not this cycle; there is deliberately no base64 branch.
    The nested path is dug directly (clean rows lack the ``_soap_text`` convenience
    key). Any artifact that is not a SOAP-bearing DocumentReference — e.g. the
    scheduling/triage conversation rows, which have no ``content[0].attachment.data``
    — returns ``None`` so :class:`RecordPresence` stays inconclusive and never
    suppresses by silence.
    """
    raw = _artifact_content(case)
    if not isinstance(raw, str):
        return None
    try:
        doc = json.loads(raw)
        data = doc["content"][0]["attachment"]["data"]
    except (TypeError, ValueError, KeyError, IndexError):
        return None
    return data if isinstance(data, str) else None


# --------------------------------------------------------------------------- #
# RecordPresence — the GROUND-FLOOR-1 suppress executor
# --------------------------------------------------------------------------- #
class RecordPresence(VerificationContract):
    """Disprove a false ``FABRICATED_HISTORY`` by GROUNDING the artifact's documented
    history in the patient record — the S-BS-7 presence-check generalized from the
    transcript to ``patient_profile.conditions``.

    Where :class:`PresenceCheck` clears ``"X not in transcript"`` by finding X in the
    transcript, this clears ``"history item X was never in the record"`` by finding
    every documented PMH item already present in the patient's condition list. A
    legitimately carried-forward PMH grounded in the record SUPPRESSES the false
    finding; a genuinely injected condition (∉ the record) leaves the finding to
    STAND. Wraps the proven :class:`InRowTool` (``extract_pmh_items`` + ``snomed_core``
    set-membership) — purpose-built, reused not rewritten.

    Conservative on three axes (never clears a true fabrication, never clears by
    silence):
      * suppress ONLY when ALL extracted PMH items are grounded (``conforms is True``);
        any ungrounded item ⇒ the WHOLE finding stands (``conforms is False``).
      * a non-SOAP / non-DocumentReference artifact (scheduling/triage rows) decodes
        to ``None`` ⇒ inconclusive, never suppressed.
      * an EMPTY PMH extraction (zero items) ⇒ inconclusive, never suppressed —
        ``InRowTool`` conforms *vacuously* on ``[]`` ("nothing to check" ≠ "all
        grounded"), so this guard is load-bearing.

    NOTE (P0 string match): ``match: snomed_core`` is a string set-membership check.
    It is sound here only because the synthetic bench mints both the note PMH and
    ``patient_profile.conditions`` from identical SNOMED FSN strings. It does NOT
    generalize to real clinical text — code-based resolution (Hermes ``snomed_code``)
    is TERMINOLOGY-1, the next phase.

    params = {"oracle_path": "patient_profile.conditions",  # required
              "extractor": "soap_pmh_items",                # required
              "match": "snomed_core",                       # required (P0 string)
              "artifact_decode": "fhir_documentreference"}  # informational
    """

    contract_type = "record_presence"

    def __init__(self, decl: VerificationContractDecl) -> None:
        self.flag_code = decl.flag_code
        self.question = decl.question
        self.version = decl.version
        self._params = decl.params

    def check(self, finding: dict[str, Any], case: dict[str, Any]) -> Verdict:
        soap = _decode_artifact_soap(case)
        if soap is None:
            return Verdict(
                disproved=False,
                reason=(
                    "artifact is not a SOAP-bearing FHIR DocumentReference "
                    "(no content[0].attachment.data); inconclusive, flag stays open"
                ),
            )

        p = self._params
        locus = p.get("locus", "")
        spec = VerificationSpec(
            tool="in_row",
            applies_to_flags=(self.flag_code,),
            locus=locus,
            reference={
                "oracle_path": p["oracle_path"],
                "extractor": p["extractor"],
                "match": p["match"],
            },
            version=self.version,
        )
        claim = Claim(
            claim_type=RECORD_PRESENCE,
            flag_code=self.flag_code,
            subject=soap,
            locus=locus,
            source=case,
        )
        result = InRowTool().verify(claim, spec)
        items_checked = int(result.evidence.get("items_checked", 0))
        if items_checked == 0:
            return Verdict(
                disproved=False,
                reason=(
                    "no PMH items extracted from the artifact; nothing to ground "
                    "(inconclusive — 'nothing to check' is not 'all grounded')"
                ),
            )
        if result.conforms is True:
            return Verdict(
                disproved=True,
                evidence=(
                    f"all {items_checked} documented PMH item(s) are grounded in "
                    f"{p['oracle_path']} (oracle_size={result.evidence.get('oracle_size')})"
                ),
                reason=(
                    f"every documented history item is present in the patient record "
                    f"({p['oracle_path']}, match={p['match']}); the FABRICATED_HISTORY "
                    f"finding is disproven by the record"
                ),
            )
        return Verdict(
            disproved=False,
            reason=(
                f"{len(result.evidence.get('ungrounded') or [])} documented history "
                f"item(s) not grounded in {p['oracle_path']} "
                f"({result.evidence.get('ungrounded')}); fabrication stands"
            ),
        )


def _dosage_reference(params: dict[str, Any]) -> dict[str, Any]:
    ref = {"dose_regex": params["dose_regex"]}
    if params.get("transcript_path"):
        ref["transcript_path"] = params["transcript_path"]
    if params.get("record_path"):
        ref["record_path"] = params["record_path"]
    return ref


# ── the pack executor-registration interface (PACK-3 D1) ───────────────────────────
# Module-level declarative dicts (D-A): no execution at import, inspectable, import-clean.
# The core merges these into its generic registries on first grounding use (lazy, D-B).
SUPPRESS_EXECUTORS: dict[str, Any] = {
    "record_presence": RecordPresence,
}
FLOOR_EXECUTORS: dict[str, FloorExecutor] = {
    "dosage_grounding": FloorExecutor(
        tool_factory=lambda http_client: DosageGroundingTool(),
        reference_builder=_dosage_reference,
    ),
}
