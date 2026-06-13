"""PACK-3 layer-3 — the core loads its clinical grounding EXECUTORS from the active
`healthcare` pack, not from the engine (healthcare-realm-as-pack, first packs-as-CODE).

The floor layer of the core↔domain boundary: the clinical executors (`RecordPresence`
suppress + `DosageGroundingTool` floor + the `InRowTool` record-presence primitive + the
SOAP/PMH/dose extractors) relocated into `packs/healthcare/floors.py`, behind the pack
executor-registration interface (`pack.load_pack_floors`). The engine
(`harness/grounding.py` + `verification/`) is domain-agnostic; it merges the pack's
`SUPPRESS_EXECUTORS` / `FLOOR_EXECUTORS` LAZILY (`suppress_executors()` /
`floor_executors()`), and the UAP-3b withstands-gate (THE MOAT, `signals.py`) reads the
merged suppress registry — so a pack-registered suppress executor is moat-visible (A4).

The boundary is grep-verifiable like layer1a/2: the clinical executor CODE is ABSENT from
the engine AND PRESENT under the pack (relocation, not deletion). A blanket domain-WORD
sweep is over-broad (the generic `PresenceCheck` legitimately reads a `dosage_regex` param
key; the `dosage_grounding` contract-type NAME is interface vocabulary the pack registers
against) — so, exactly as PACK-1/2 asserted specific relocated *artifacts* (path literals)
with documented carve-outs, this asserts specific clinical CODE needles with a CLOSED,
enumerated carve-out for the irreducible generic residual.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from lithrim_bench.harness import grounding, pack
from lithrim_bench.harness.ontology import from_dict, load_ontology
from lithrim_bench.runtime.council.signals import build_judge_signals

REPO_ROOT = Path(__file__).resolve().parents[1]
ENGINE_DIRS = (
    REPO_ROOT / "lithrim_bench" / "harness",
    REPO_ROOT / "lithrim_bench" / "verification",
)
PACK_FLOORS = REPO_ROOT / "packs" / "healthcare" / "floors.py"
CALIB = REPO_ROOT / "examples" / "judge_calib_v1.jsonl"

CLEAN_ID = "bench_scribe_v1_clean_negative_aaecd73c3bcf"
VIOL_ID = "bench_scribe_v1_inject_condition_1bd0f10dc7b5"

# The CLINICAL executor CODE that relocated. These are unambiguous executor code (class /
# def / extractor & match-strategy literals) — not domain words that legitimately recur in
# generic code. A re-introduced clinical executor in the engine trips these.
_CLINICAL_CODE_NEEDLES = (
    "class RecordPresence",
    "class InRowTool",
    "class DosageGroundingTool",
    "def extract_pmh_items",
    "def extract_plan_dose_tokens",
    "def _decode_artifact_soap",
    '"soap_pmh_items"',
    '"snomed_core"',
    '"dose_token"',
)

# The CLOSED carve-out: the ONLY markers that may remain when a blanket domain-word sweep is
# run over the engine. Each is justified:
#   (i)   dosage_regex / _dosage_re — the generic PresenceCheck's extraction param key + attr
#         (a FROZEN ontology-contract key; renaming it would edit pinned contract data).
#   (ii)  dosage_grounding / TOOL_DOSAGE_GROUNDING / dose_regex — the floor contract-type NAME
#         constant + its required-reference key: the interface VOCABULARY the pack registers
#         against (stays in spec.py; referenced by the engine's floor docstrings).
#   (iii) patient_profile.active_medications — the generic `_resolve_path` docstring EXAMPLE.
_CARVEOUT_MARKERS = (
    "dosage_regex",
    "_dosage_re",
    "dosage_grounding",
    "TOOL_DOSAGE_GROUNDING",
    "dose_regex",
    "patient_profile.active_medications",
)
_BROAD_SWEEP = (
    "snomed",
    "pmh",
    "dosage",
    "patient_profile",
    "soap_pmh",
    "active_medications",
    "soap",
)


def _iter_py(roots) -> list[Path]:
    files: list[Path] = []
    for root in roots if isinstance(roots, tuple) else (roots,):
        files += [root] if root.is_file() else sorted(root.rglob("*.py"))
    return [f for f in files if "__pycache__" not in f.parts]


def _grep(roots, needles: tuple[str, ...], *, ignore_case: bool = False) -> list[str]:
    low = tuple(n.lower() for n in needles)
    out: list[str] = []
    for f in _iter_py(roots):
        for i, line in enumerate(f.read_text().splitlines(), 1):
            hay = line.lower() if ignore_case else line
            if any(n in hay for n in (low if ignore_case else needles)):
                out.append(f"{f.relative_to(REPO_ROOT)}:{i}: {line.strip()}")
    return out


# ───────────────────────────── D5 / A1 — the boundary ─────────────────────────────
def test_engine_carries_no_clinical_executor_code():
    """The domain-agnostic engine carries NO clinical executor code."""
    hits = _grep(ENGINE_DIRS, _CLINICAL_CODE_NEEDLES)
    assert hits == [], "the engine still carries clinical executor code:\n" + "\n".join(hits)


def test_clinical_executors_live_in_the_pack():
    """…AND the clinical executors are PRESENT under the pack — relocation, not deletion.
    (Fails if a clinical executor was silently dropped rather than moved home.)"""
    present = {n for n in _CLINICAL_CODE_NEEDLES if _grep(PACK_FLOORS, (n,))}
    missing = sorted(set(_CLINICAL_CODE_NEEDLES) - present)
    assert missing == [], "clinical executor code missing from the pack (dropped?):\n" + "\n".join(
        missing
    )


def test_broad_domain_sweep_residual_is_the_closed_carveout():
    """A blanket domain-word sweep over the engine is over-broad; document the residual as a
    CLOSED, enumerated carve-out (not a vague 'grep minus patterns'). Non-vacuous: the sweep
    genuinely hits (the carve-out is real), and EVERY hit is justified by a closed marker."""
    residual = _grep(ENGINE_DIRS, _BROAD_SWEEP, ignore_case=True)
    assert residual, "the broad sweep found nothing — the carve-out assertion would be vacuous"
    unjustified = [h for h in residual if not any(m in h for m in _CARVEOUT_MARKERS)]
    assert unjustified == [], (
        "a domain-word hit in the engine is NOT in the closed carve-out "
        "(new clinical leak, or scrub the prose):\n" + "\n".join(unjustified)
    )


# ───────────────── D1/D2/D3 / A3 — the registration interface (non-vacuous) ─────────────────
def test_pack_floors_register_the_clinical_executors():
    mod = pack.load_pack_floors()
    assert mod is not None
    # TOOL-2 added snomed_subsumption (code-based record-presence over the Hermes MCP terminology
    # server) alongside the original snomed_core record_presence.
    assert set(mod.SUPPRESS_EXECUTORS) == {"record_presence", "snomed_subsumption"}
    assert set(mod.FLOOR_EXECUTORS) == {"dosage_grounding"}
    # merged into the engine's registries (core-generic ∪ pack)
    assert "record_presence" in grounding.suppress_executors()
    assert "record_presence" not in grounding._CONTRACT_EXECUTORS  # from the pack, not core
    assert {"structural_jute", "jute_gen", "dosage_grounding"} <= grounding.floor_contract_types()
    assert "dosage_grounding" not in grounding._core_floor_executors()  # from the pack, not core


def test_no_floors_pack_degrades_to_the_generic_engine(monkeypatch):
    """A pack that declares no `floors` runs the core-generic engine alone — the
    registration interface is non-vacuous (unregister → the clinical executors disappear)."""
    monkeypatch.setattr(grounding, "_pack_registries", lambda _pack: ({}, {}))
    assert grounding.suppress_executors() == dict(grounding._CONTRACT_EXECUTORS)
    assert "record_presence" not in grounding.suppress_executors()
    assert "dosage_grounding" not in grounding.floor_contract_types()
    # and load_pack_floors itself returns None for a manifest with no "floors"
    monkeypatch.setattr(pack, "_manifest", lambda _p: {"floors": None})
    pack._load_pack_floors.cache_clear()
    assert pack.load_pack_floors("anything") is None


def test_unknown_contract_type_fails_closed():
    """ground()'s partition guard still raises on a contract_type no executor (core OR pack)
    handles — the fail-closed core invariant survives the registry refactor."""
    data = json.loads((REPO_ROOT / "packs" / "healthcare" / "ontology.json").read_text())
    data["verification_contracts"].append(
        {
            "contract_type": "NOPE_not_an_executor",
            "flag_code": "FABRICATED_HISTORY",
            "question": "?",
            "version": "v0",
            "params": {},
        }
    )
    ont = from_dict(data)
    with pytest.raises(ValueError, match="no executor registered"):
        grounding.ground({"verdict": "PASS", "findings": []}, {}, ontology=ont)


# ───────────────────────── A2 / A4 — byte-behavior + moat-visible ─────────────────────────
def _load_case(cid: str) -> dict:
    for line in CALIB.read_text().splitlines():
        if line.strip() and (json.loads(line).get("case_id") or json.loads(line).get("id")) == cid:
            return json.loads(line)
    raise AssertionError(f"case {cid} not in {CALIB}")


def _fab_result() -> dict:
    return {
        "verdict": "BLOCK",
        "findings": [
            {"code": "FABRICATED_HISTORY", "severity": "HIGH", "detail": "PMH fabricated"}
        ],
    }


def test_ground_byte_behavior_identical_on_the_demo_pair():
    """A2: ground() — flowing through the PACK-merged registry — still suppresses the false
    FABRICATED_HISTORY on the clean case (BLOCK→PASS) and lets it STAND on the injected case
    (BLOCK→BLOCK). The executors moved home; the behavior did not change."""
    ont = load_ontology()
    g_clean = grounding.ground(_fab_result(), _load_case(CLEAN_ID), ontology=ont)
    assert g_clean.original_verdict == "BLOCK" and g_clean.verdict == "PASS"
    assert {s["finding"]["code"] for s in g_clean.suppressed} == {"FABRICATED_HISTORY"}

    g_viol = grounding.ground(_fab_result(), _load_case(VIOL_ID), ontology=ont)
    assert g_viol.verdict == "BLOCK" and g_viol.suppressed == []


def test_moat_sees_the_pack_record_presence_and_unregister_loses_it(monkeypatch):
    """A4: the withstands-gate (signals.py) reads the pack-merged suppress registry, so the
    pack's record_presence runs pre-consensus — suppressing the false FABRICATED_HISTORY on
    the clean case, standing on the injected case. NON-VACUOUS: drop the pack registry and the
    record_presence validator signal disappears (proves it is pack-sourced, not core)."""
    ont = load_ontology()
    seam = {"findings": [{"taxonomy_code": "FABRICATED_HISTORY", "evidence_spans": []}]}

    for cid, expect_disproved in [(CLEAN_ID, True), (VIOL_ID, False)]:
        sig = build_judge_signals(
            copy.deepcopy(seam), role="faithfulness_judge", ontology=ont, case=_load_case(cid)
        )
        rp = [v for v in sig.validator_outputs if v.contract_type == "record_presence"]
        assert len(rp) == 1, f"{cid}: the moat did not see the pack's record_presence"
        assert rp[0].disproved is expect_disproved

    # unregister the pack floors → the moat loses the record_presence signal entirely.
    monkeypatch.setattr(grounding, "_pack_registries", lambda _pack: ({}, {}))
    sig = build_judge_signals(
        copy.deepcopy(seam), role="faithfulness_judge", ontology=ont, case=_load_case(CLEAN_ID)
    )
    assert [v for v in sig.validator_outputs if v.contract_type == "record_presence"] == []
