"""NARR-3 — the deterministic narrative floor executors + ATTACH-VALIDATORS.

Three pure-stdlib `in_process` floor tools ship in `packs/narrative/floors.py`
and inject a BLOCK the council missed (the FLOOR direction, run by `_run_floor`
in `harness/grounding.py`):

  * ``bracket_leak``       — an instruction marker (`[READER FEELING ...]`) leaked
                             into the shipped scene.
  * ``length_violation``   — the preamble is not the required 3-4 sentences.
  * ``silent_degradation`` — a content-filtered / non-`stop` generation silently
                             demoted to the baseline yet shipped as final (the
                             day-one headline proof; reads provenance off the
                             case row via ``claim.source``).

The acceptance tests are written FIRST (RED): the floor tools + the three
``_KNOWN_TOOLS`` registrations + the ontology ``verification_contracts`` do not
exist yet, so ``VerificationSpec`` raises "unknown tool" and the executors are
absent. A1..A6 map to the driver §5 acceptance criteria.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PACK_DIR = REPO_ROOT / "packs" / "narrative"
FLOORS_PATH = PACK_DIR / "floors.py"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "narrative" / "storyworld_session.json"
PACK = "narrative"

# the degraded-scene values that drive the day-one SILENT_DEGRADATION proof
_DEGRADED = json.loads(FIXTURE.read_text())["resource"]["metadata"]["enhanced_scenes"][
    "scene_content_filtered_fallback"
]


def _load_floors():
    """Importlib-load packs/narrative/floors.py by path (mirrors load_pack_floors)."""
    spec = importlib.util.spec_from_file_location("narrative_floors_under_test", FLOORS_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _claim(subject, *, source=None):
    from lithrim_bench.verification import STRUCTURAL_CONFORMANCE, Claim

    return Claim(
        claim_type=STRUCTURAL_CONFORMANCE,
        flag_code=None,
        subject=subject,
        locus="",
        source=source or {},
    )


def _spec(tool, reference):
    from lithrim_bench.verification import VerificationSpec

    return VerificationSpec(
        tool=tool,
        applies_to_flags=("X",),
        locus="",
        reference=reference,
        version="v1",
    )


# ── A1 — bracket_leak fires (and is MARKER-targeted, not any bracket pair) ──


def test_bracket_leak_violation_and_clean():
    floors = _load_floors()
    tool = floors.BracketLeakTool()
    spec = _spec("bracket_leak", {})

    leaked = "She turned to the window. [READER FEELING: tense] The night gave no answer."
    assert tool.verify(_claim(leaked), spec).conforms is False

    clean = (
        "She turned to the window. The night gave no answer, only the long road "
        "back down the mountain."
    )
    assert tool.verify(_claim(clean), spec).conforms is True

    # a legitimate lowercase in-prose bracket must NOT fire — proves the marker-targeting
    in_prose = "He read the sign by the well [it was faded] and pressed on into the dark."
    assert tool.verify(_claim(in_prose), spec).conforms is True

    # non-str / empty subject -> inconclusive, never flips by silence
    assert tool.verify(_claim(""), spec).conforms is None
    assert tool.verify(_claim(None), spec).conforms is None


# ── A2 — length_violation fires ──


def test_length_violation_and_clean():
    floors = _load_floors()
    tool = floors.LengthViolationTool()
    spec = _spec("length_violation", {"min_sentences": 3, "max_sentences": 4})

    one = "The confrontation unfolded near the old well where the family had once drawn water."
    assert tool.verify(_claim(one), spec).conforms is False

    six = "A. B. C. D. E. F."
    assert tool.verify(_claim(six), spec).conforms is False

    three = "She turned to the window. The night gave no answer. The road waited below."
    assert tool.verify(_claim(three), spec).conforms is True

    four = "One thing. Two things. Three things. Four things."
    assert tool.verify(_claim(four), spec).conforms is True

    assert tool.verify(_claim(""), spec).conforms is None


# ── A3 — silent_degradation fires (the headline; provenance off the case row) ──


def test_silent_degradation_violation_clean_and_inconclusive():
    floors = _load_floors()
    tool = floors.SilentDegradationTool()
    spec = _spec("silent_degradation", {})
    subject = _DEGRADED["clean_text"]

    # violation: the day-one degraded scene (content_filter + baseline)
    degraded_source = {"finish_reason": "content_filter", "source": _DEGRADED["source"]}
    assert _DEGRADED["source"] == "baseline"
    assert tool.verify(_claim(subject, source=degraded_source), spec).conforms is False

    # clean: a complete generation (stop + enhanced)
    clean_source = {"finish_reason": "stop", "source": "enhanced"}
    assert tool.verify(_claim(subject, source=clean_source), spec).conforms is True

    # a non-stop finish that was NOT demoted to baseline is not a silent demotion
    enhanced_filtered = {"finish_reason": "content_filter", "source": "enhanced"}
    assert tool.verify(_claim(subject, source=enhanced_filtered), spec).conforms is True

    # inconclusive: provenance fields absent -> never flip by silence
    assert tool.verify(_claim(subject, source={}), spec).conforms is None
    assert tool.verify(_claim(subject, source={"finish_reason": "stop"}), spec).conforms is None
    assert tool.verify(_claim(subject, source={"source": "baseline"}), spec).conforms is None


# ── A4 — the floor flips the verdict via ground() ──

_NARRATIVE_ONT_DICT = {
    "ontology_version": "narrative_floor_test_v1",
    "domain": "narrative",
    "flags": [
        {
            "flag": "SILENT_DEGRADATION",
            "category": "provenance",
            "definition": "",
            "when_to_use": "",
            "when_NOT_to_use": "",
            "owner_roles": ["risk_judge"],
            "tier": "TIER_1",
            "gradeable": True,
        },
        {
            "flag": "BRACKET_LEAK",
            "category": "contract",
            "definition": "",
            "when_to_use": "",
            "when_NOT_to_use": "",
            "owner_roles": ["policy_judge"],
            "tier": "TIER_1",
            "gradeable": True,
        },
        {
            "flag": "LENGTH_VIOLATION",
            "category": "contract",
            "definition": "",
            "when_to_use": "",
            "when_NOT_to_use": "",
            "owner_roles": [],
            "tier": "TIER_2",
            "gradeable": True,
        },
    ],
    "questions": [],
    "verification_contracts": [
        {
            "flag_code": "SILENT_DEGRADATION",
            "question": "Was the scene a complete generation, not a silently-demoted baseline?",
            "contract_type": "silent_degradation",
            "version": "v1",
            "params": {"inject_flag_code": "SILENT_DEGRADATION", "inject_severity": "HIGH"},
        },
        {
            "flag_code": "BRACKET_LEAK",
            "question": "Is the scene free of leaked instruction markers?",
            "contract_type": "bracket_leak",
            "version": "v1",
            "params": {"inject_flag_code": "BRACKET_LEAK", "inject_severity": "HIGH"},
        },
        {
            "flag_code": "LENGTH_VIOLATION",
            "question": "Is the preamble 3-4 sentences?",
            "contract_type": "length_violation",
            "version": "v1",
            "params": {
                "inject_flag_code": "LENGTH_VIOLATION",
                "inject_severity": "MEDIUM",
                "min_sentences": 3,
                "max_sentences": 4,
            },
        },
    ],
    "severity_map": {
        "weights": {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.2},
        "block_at_or_above": 0.5,
        "warn_above": 0.0,
    },
}

_COUNCIL_PASS = {
    "verdict": "PASS",
    "findings": [],
    "semantic": {"judge_votes": [{"judge_role": "risk_judge", "vote": "PASS", "findings": []}]},
}


def _narrative_floor_ontology():
    from lithrim_bench.harness.ontology import from_dict

    return from_dict(_NARRATIVE_ONT_DICT)


def test_silent_degradation_flips_pass_to_block():
    from lithrim_bench.harness.grounding import ground
    from lithrim_bench.harness.report import composite

    ont = _narrative_floor_ontology()
    scene = _DEGRADED["clean_text"]

    degraded_case = {
        "artifacts": [{"type": "narrative_scene", "content": scene}],
        "finish_reason": "content_filter",
        "source": "baseline",
    }
    g = ground(_COUNCIL_PASS, degraded_case, ontology=ont)
    assert g.original_verdict == "PASS" and g.verdict == "BLOCK"
    assert composite(g)["verdict"] == "reject"
    injected = [b for b in g.floor_blocks if b["injected_finding"] is not None]
    codes = {b["injected_finding"]["code"] for b in injected}
    assert "SILENT_DEGRADATION" in codes
    assert "SILENT_DEGRADATION" in [f.get("code") for f in g.active]


def test_clean_case_stays_pass_floor_blocks_empty():
    from lithrim_bench.harness.grounding import ground
    from lithrim_bench.harness.report import composite

    ont = _narrative_floor_ontology()
    clean_scene = (
        "She turned to the window. The night gave no answer, only the long road. "
        "The headlights swung across bare rock and held."
    )
    clean_case = {
        "artifacts": [{"type": "narrative_scene", "content": clean_scene}],
        "finish_reason": "stop",
        "source": "enhanced",
    }
    g = ground(_COUNCIL_PASS, clean_case, ontology=ont)
    assert g.verdict == "PASS"
    assert composite(g)["verdict"] == "approve"
    assert [b for b in g.floor_blocks if b["injected_finding"] is not None] == []


def test_inconclusive_silent_degradation_never_flips():
    from lithrim_bench.harness.grounding import ground

    ont = _narrative_floor_ontology()
    clean_scene = (
        "She turned to the window. The night gave no answer, only the long road. "
        "The headlights swung across bare rock and held."
    )
    # provenance ABSENT -> silent_degradation inconclusive; the other floors clean
    inconclusive_case = {"artifacts": [{"type": "narrative_scene", "content": clean_scene}]}
    g = ground(_COUNCIL_PASS, inconclusive_case, ontology=ont)
    assert g.verdict == "PASS"
    sd = [
        b
        for b in g.floor_blocks
        if b["decl"].contract_type == "silent_degradation"
    ]
    assert len(sd) == 1 and sd[0]["injected_finding"] is None


# ── A5 — admissibility, pack-bound, zero leakage (subprocess pack=narrative) ──

_GRADE_SCRIPT = r"""
import json
import sys

_opened = []


def _audit(event, args):
    if event == "open" and args and isinstance(args[0], (str, bytes)):
        p = args[0].decode() if isinstance(args[0], bytes) else args[0]
        _opened.append(p)


sys.addaudithook(_audit)

from lithrim_bench.harness.grounding import ground
from lithrim_bench.harness.ontology import load_ontology
from lithrim_bench.harness.pack import active_pack, pack_ontology_path
from lithrim_bench.harness.report import composite
from lithrim_bench.picklist import load_case

CASE_ID = "narrative_jinn_silent_degradation"
CASE_SRC = "packs/narrative/examples/narrative_v1.jsonl"

ont = load_ontology(pack_ontology_path())
case = load_case(CASE_ID, source=CASE_SRC)
assert case is not None, "narrative violation case did not load"

COUNCIL_PASS = {
    "verdict": "PASS",
    "findings": [],
    "semantic": {"judge_votes": [{"judge_role": "risk_judge", "vote": "PASS", "findings": []}]},
}
g = ground(COUNCIL_PASS, case, ontology=ont)
comp = composite(g)


def _norm(p):
    return p.replace("\\", "/")


healthcare_reads = sorted({_norm(p) for p in _opened if "packs/healthcare" in _norm(p)})

print("__JSON__" + json.dumps({
    "active_pack": active_pack(),
    "n_verification_contracts": len(ont.contracts),
    "stage_verdict": g.verdict,
    "verdict": comp["verdict"],
    "active_codes": [f.get("code") for f in g.active],
    "floor_block_count": comp["floor_block_count"],
    "healthcare_reads": healthcare_reads,
}))
"""


def _run_grade() -> dict:
    env = dict(os.environ)
    env["LITHRIM_BENCH_PACK"] = PACK
    proc = subprocess.run(
        [sys.executable, "-c", _GRADE_SCRIPT],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"narrative floor grade subprocess failed:\n--- STDOUT ---\n{proc.stdout}\n--- STDERR ---\n{proc.stderr}"
    )
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("__JSON__")), None)
    assert line is not None, f"no __JSON__ payload:\n{proc.stdout}\n{proc.stderr}"
    return json.loads(line[len("__JSON__") :])


def test_narrative_floor_grades_under_pack_narrative():
    out = _run_grade()
    assert out["active_pack"] == PACK
    assert out["n_verification_contracts"] == 3
    assert out["stage_verdict"] == "BLOCK"
    assert out["verdict"] == "reject"
    assert "SILENT_DEGRADATION" in out["active_codes"]
    assert out["floor_block_count"] >= 1
    assert out["healthcare_reads"] == [], f"healthcare leaked under pack=narrative: {out['healthcare_reads']}"


# ── A6 — moat + clinical floor regression-clean (_KNOWN_TOOLS additive) ──


def test_known_tools_additive_and_three_new_registered():
    from lithrim_bench.verification import spec as spec_mod

    prior = {
        spec_mod.TOOL_IN_ROW,
        spec_mod.TOOL_STRUCTURAL_JUTE,
        spec_mod.TOOL_RECORD_RAG,
        spec_mod.TOOL_KB_RAG,
        spec_mod.TOOL_JUTE_GEN,
        spec_mod.TOOL_DOSAGE_GROUNDING,
    }
    assert prior <= spec_mod._KNOWN_TOOLS, "the 6 prior tools must remain (additive, not replaced)"

    new = {
        spec_mod.TOOL_BRACKET_LEAK,
        spec_mod.TOOL_LENGTH_VIOLATION,
        spec_mod.TOOL_SILENT_DEGRADATION,
    }
    assert new <= spec_mod._KNOWN_TOOLS, "the 3 narrative floor tool-names must be registered"
    assert prior.isdisjoint(new)
    # the prior tools' required-reference-key shapes are untouched
    assert spec_mod._REQUIRED_REFERENCE_KEYS[spec_mod.TOOL_DOSAGE_GROUNDING] == {"dose_regex"}
    assert spec_mod._REQUIRED_REFERENCE_KEYS[spec_mod.TOOL_LENGTH_VIOLATION] == {
        "min_sentences",
        "max_sentences",
    }
    assert spec_mod._REQUIRED_REFERENCE_KEYS[spec_mod.TOOL_BRACKET_LEAK] == set()
    assert spec_mod._REQUIRED_REFERENCE_KEYS[spec_mod.TOOL_SILENT_DEGRADATION] == set()
