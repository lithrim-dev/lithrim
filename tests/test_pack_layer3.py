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

from pathlib import Path

from lithrim_bench.harness import grounding, pack

REPO_ROOT = Path(__file__).resolve().parents[1]
ENGINE_DIRS = (
    REPO_ROOT / "lithrim_bench" / "harness",
    REPO_ROOT / "lithrim_bench" / "verification",
)

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
#   (iv)  REL-5e (BL-4) — the SNOMED-battery/argshape interface vocabulary (TOOL-2 onward):
#         snomed_battery + SnomedBatteryGrounding (the generic MCP-terminology contract type
#         + its executor class, engine-resident by design like `dosage_grounding`),
#         snomed_subsumption (the PACK-registered executor NAME the engine merges + the
#         readiness/boundary docstrings naming it), snomed_oracle (the argshape gate's
#         terminology-fact-source callable param), hermes_snomed (a tool-id EXAMPLE in a
#         params docstring), and the "SNOMED MCP tool" / "SNOMED semantic tag" docstring
#         phrases describing that interface. All identifier-anchored CODE vocabulary/prose —
#         zero clinical data (no codes, meds, doses, or patient content).
_CARVEOUT_MARKERS = (
    "dosage_regex",
    "_dosage_re",
    "dosage_grounding",
    "TOOL_DOSAGE_GROUNDING",
    "dose_regex",
    "patient_profile.active_medications",
    "snomed_battery",
    "SnomedBatteryGrounding",
    "snomed_subsumption",
    "snomed_oracle",
    "hermes_snomed",
    "SNOMED MCP tool",
    "SNOMED semantic tag",
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
    # CONCEPT-PRESERVATION-1 (pack 0fd3e4b) added the concept_preservation floor.
    assert set(mod.FLOOR_EXECUTORS) == {"dosage_grounding", "concept_preservation"}
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


# PACK-DIST-2 D5: the funcs that read the pack's floors/ontology/demo-pair corpus directly
# (test_clinical_executors_live_in_the_pack + test_unknown_contract_type_fails_closed +
# test_ground_byte_behavior_identical_on_the_demo_pair + test_moat_sees_the_pack_record_presence_…)
# relocated to the pack repo (tests/test_pack_layer3_relocated.py). The generic engine-boundary
# funcs + the NEEDS_PACK registration func (test_pack_floors_register_the_clinical_executors) stay.
