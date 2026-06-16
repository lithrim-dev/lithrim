"""NARR-1 — the `narrative` domain pack (the eval-anything CE wedge, SPEC_NARRATIVE_EVAL Phase 1).

Proves a genuinely INDEPENDENT non-clinical NARRATIVE pack (``packs/narrative/`` — its OWN
ontology + council_roles + taxonomy, ZERO ``packs/healthcare/`` reuse, mirroring
``packs/support_ticket_qa/``) is admissible and grades a StoryWorld scene to a verdict through the
AUTHORED path with the healthcare pack UNLOADED and ``:8002`` DOWN, at $0 via injected mock
predictors. DATA-ONLY: this pack ships no engine/BFF/shell change — the workspace/pack UI already
exists (``apps/shell/src/app.jsx``), so a ``pack='narrative'`` workspace is creatable today.

Two gates:
  * the pure-JSON snapshot/ontology CONSISTENCY (the contract-of-record; runs in any interpreter), and
  * the authored-path GRADE (mirrors ``tests/test_standalone_ce.py`` — gated on the ``[council]`` extra,
    run in ``debuglithrim``; the $0 marker-keyed predictor makes the verdict flip the AUTHORING).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PACK_DIR = REPO_ROOT / "packs" / "narrative"
SNAP = PACK_DIR / "taxonomy_snapshot.json"
ONTO = PACK_DIR / "ontology.json"
PACK = "narrative"

_TIER_KEY_TO_FLAG_TIER = {
    "TIER_1_NEVER_EVENTS": "TIER_1",
    "TIER_2_HIGH_RISK": "TIER_2",
    "TIER_3_MEDIUM": "TIER_3",
}

# The SPEC §2.1 clinical needles — inverted-green (we assert ZERO hits in the rendered narrative prompts).
CLINICAL_NEEDLES = re.compile(
    r"HIPAA|patient|medication|dosage|allerg|clinical|SOAP|escalat|consent|transcript",
    re.IGNORECASE,
)


# ── A-NARR-1: the snapshot is an internally-consistent contract-of-record (pure JSON, $0) ──


def test_narrative_snapshot_consistency():
    snap = json.loads(SNAP.read_text())
    ont = json.loads(ONTO.read_text())

    tiers = snap["tiers"]
    tier_union = set().union(*tiers.values())
    tier_of = {code: _TIER_KEY_TO_FLAG_TIER[k] for k, codes in tiers.items() for code in codes}
    lenses = snap["lenses"]
    prod = set(snap["production_judges"])

    # production_judges = the 3 CORE deployable role names (PACK-2c: no new deployable judge)
    assert prod == {"risk_judge", "policy_judge", "faithfulness_judge"}

    # every lens belongs to a production judge; every lens code is a real tier code (emit authority)
    lens_codes: set[str] = set()
    for role, codes in lenses.items():
        assert role in prod, f"lens role {role!r} not in production_judges"
        for c in codes:
            assert c in tier_union, f"lens code {c!r} (role {role}) is in no tier"
            lens_codes.add(c)

    # tier1_owners: each code is TIER_1, each owner is a production judge AND can emit it (in its lens)
    t1 = set(tiers["TIER_1_NEVER_EVENTS"])
    for code, owners in snap["tier1_owners"].items():
        assert code in t1, f"tier1_owner code {code!r} is not TIER_1"
        for owner in owners:
            assert owner in prod, f"tier1 owner {owner!r} not in production_judges"
            assert code in lenses.get(owner, []), f"tier1 owner {owner!r} cannot emit {code!r} (not in lens)"
    for code in t1:
        assert code in snap["tier1_owners"], f"TIER_1 never-event {code!r} has no owner"

    # every gradeable ontology flag: in the snapshot tier union (admissibility) + in some lens (not
    # inert) + its tier matches the snapshot + any declared owner is non-inert
    gradeable = [f for f in ont["flags"] if f.get("gradeable")]
    assert len(gradeable) >= 10, f"expected the full narrative taxonomy, got {len(gradeable)} gradeable flags"
    for f in gradeable:
        code = f["flag"]
        assert code in tier_union, f"gradeable flag {code!r} not in the snapshot tiers (would 422 admissibility)"
        assert code in lens_codes, f"gradeable flag {code!r} is in no lens — no judge can raise it (inert)"
        assert f["tier"] == tier_of[code], f"flag {code!r} tier {f['tier']!r} != snapshot {tier_of[code]!r}"
        for owner in f.get("owner_roles", []):
            assert owner in prod and code in lenses.get(owner, []), f"flag {code!r} owner {owner!r} is inert"

    # NARR-3 attached the deterministic FLOOR contracts; NARR-4 (S-BS-NARR3-3) demoted
    # LENGTH_VIOLATION out of the floor → the policy_judge lens, leaving 2 floor contracts
    # (bracket_leak, silent_degradation). Each must reference a real floor flag in the snapshot
    # and carry the inject_flag_code/inject_severity the floor dispatch reads (was [] in NARR-1).
    _NARR3_FLOOR_TYPES = {"bracket_leak", "silent_degradation"}
    contracts = ont["verification_contracts"]
    assert {c["contract_type"] for c in contracts} == _NARR3_FLOOR_TYPES, (
        "NARR-4 declares exactly the 2 deterministic floor contracts (LENGTH_VIOLATION demoted)"
    )
    for c in contracts:
        assert c["flag_code"] in tier_union, f"floor contract flag {c['flag_code']!r} not in the snapshot tiers"
        assert c["params"]["inject_flag_code"] == c["flag_code"], "inject_flag_code must match the floor flag"
        assert c["params"]["inject_severity"] in {"HIGH", "MEDIUM", "LOW"}

    # the snapshot tier union and the gradeable-flag set are the same contract (no orphan codes)
    assert {f["flag"] for f in gradeable} == tier_union, "ontology gradeable flags must equal the snapshot tier union"


def test_narrative_pack_manifest_discoverable():
    """A1e: a valid tier:core / domain:narrative manifest whose refs resolve — so discover_packs()
    (and thus GET /v1/packs → the shell pack-picker) lists it. Pure JSON ($0)."""
    manifest = json.loads((PACK_DIR / "pack.json").read_text())
    assert manifest["pack_id"] == PACK
    assert manifest["tier"] == "core"
    assert manifest["domain"] == "narrative"
    assert (PACK_DIR / manifest["ontology"]).is_file()
    assert (PACK_DIR / manifest["flags_ref"]).is_file()
    roles_dir = PACK_DIR / manifest["council_roles"]
    for role in manifest["judges"]:
        assert (roles_dir / f"{role}.txt").is_file(), f"missing council role prompt for {role}"


# ── A-NARR-2..4: the authored path grades a StoryWorld scene to a verdict (mirrors test_standalone_ce) ──

_GRADE_SCRIPT = r"""
import json
import sys

_opened = []


def _audit(event, args):
    if event == "open" and args and isinstance(args[0], (str, bytes)):
        p = args[0].decode() if isinstance(args[0], bytes) else args[0]
        _opened.append(p)


sys.addaudithook(_audit)

from lithrim_bench.harness.pack import (
    active_pack,
    pack_lenses,
    pack_ontology_path,
    pack_production_judges,
    pack_prompts_path,
)
from lithrim_bench.harness.ontology import load_ontology
from lithrim_bench.harness.grade import grade_inprocess
from lithrim_bench.harness.grounding import ground
from lithrim_bench.harness.report import composite
from lithrim_bench.picklist import load_case
from lithrim_bench.runtime.council.authored_stage import build_authored_semantic_stage
from lithrim_bench.runtime.council.judge_assignment import render_role_questions
from lithrim_bench.runtime.council.judges_dspy import V2_ROLES, build_judge_lm

CASE_ID = "narrative_jinn_exposure_clean"
CASE_SRC = "packs/narrative/examples/narrative_v1.jsonl"
ROLE = "policy_judge"
FLAG = "BRACKET_LEAK"
MARKER = "=== AUTHORED REFINEMENT (ontology assignment) ==="

ont = load_ontology(pack_ontology_path())
case = load_case(CASE_ID, source=CASE_SRC)
assert case is not None, "narrative case did not load"


def _approve(*, role_key_questions="", **_kw):
    return {"decision": "approve", "findings": []}


def _block_on_marker(role):
    def _p(*, role_key_questions="", **_kw):
        if role == ROLE and MARKER in role_key_questions:
            return {
                "decision": "reject",
                "findings": [{
                    "taxonomy_code": FLAG,
                    "evidence_spans": [{"quote": "square-bracket marker", "turn_ids": []}],
                }],
            }
        return {"decision": "approve", "findings": []}

    return _p


# clean grade: no assignment -> each judge defaults to its full pack lens; all approve -> approve
clean_stage = build_authored_semantic_stage(
    ontology=ont, assignments={}, predictors={r: _approve for r in V2_ROLES}
)
rc = grade_inprocess(case, semantic_stage=clean_stage)
verdict_clean = composite(ground(rc, case, ontology=ont))["verdict"]

# flagged grade: assign BRACKET_LEAK -> policy_judge blocks (Tier-1 one-strike) -> reject
flag_stage = build_authored_semantic_stage(
    ontology=ont, assignments={ROLE: [FLAG]}, predictors={r: _block_on_marker(r) for r in V2_ROLES}
)
rf = grade_inprocess(case, semantic_stage=flag_stage)
comp = composite(ground(rf, case, ontology=ont))
votes = {
    v["judge_role"]: {"vote": v["vote"], "findings": list(v.get("findings") or [])}
    for v in rf["semantic"]["judge_votes"]
}

rendered = {
    role: render_role_questions(ont, role, assigned_flags=sorted(pack_lenses().get(role, [])))
    for role in pack_production_judges()
}


def _norm(p):
    return p.replace("\\", "/")


healthcare_reads = sorted({_norm(p) for p in _opened if "packs/healthcare" in _norm(p)})

print("__JSON__" + json.dumps({
    "active_pack": active_pack(),
    "prompts_dir": _norm(str(pack_prompts_path())),
    "ontology_path": _norm(str(pack_ontology_path())),
    "n_verification_contracts": len(ont.contracts),
    "verdict_clean": verdict_clean,
    "verdict_flagged": comp["verdict"],
    "votes": votes,
    "rendered": rendered,
    "healthcare_reads": healthcare_reads,
    "build_judge_lm_callable": callable(build_judge_lm),
}))
"""


def _run_grade() -> dict:
    import pytest

    pytest.importorskip("openai")
    pytest.importorskip("dspy")
    env = dict(os.environ)
    env["LITHRIM_BENCH_PACK"] = PACK
    env.setdefault("OPENAI_API_KEY", "test-offline-key")
    env.setdefault("LITHRIM_LLM_PROVIDER", "openai")
    proc = subprocess.run(
        [sys.executable, "-c", _GRADE_SCRIPT],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"narrative grade subprocess failed:\n--- STDOUT ---\n{proc.stdout}\n--- STDERR ---\n{proc.stderr}"
    )
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("__JSON__")), None)
    assert line is not None, f"no __JSON__ payload:\n{proc.stdout}\n{proc.stderr}"
    return json.loads(line[len("__JSON__") :])


def test_narrative_authored_path_grades_to_a_verdict():
    """A-NARR-2: a StoryWorld scene grades through the authored path under pack=narrative. A clean
    scene with no assignment -> approve; assigning BRACKET_LEAK to its owner (policy_judge) -> that
    judge BLOCKs -> Tier-1 one-strike -> composite reject (the move is the AUTHORING). A-NARR-3:
    NARR-3 attaches 3 pure-stdlib in_process floor contracts, so the grade still never reaches
    :8002 (the clean scene is length-clean + complete-generation, so none fire). A-NARR-4: ZERO
    packs/healthcare reads."""
    out = _run_grade()
    assert out["active_pack"] == PACK
    assert f"/packs/{PACK}/" in out["prompts_dir"]
    assert f"/packs/{PACK}/" in out["ontology_path"]

    assert out["verdict_clean"] == "approve", "a clean narrative scene should grade to approve"
    assert out["verdict_flagged"] == "reject", "BRACKET_LEAK assigned to policy_judge should reject"
    policy = out["votes"]["policy_judge"]
    assert policy["vote"] == "BLOCK"
    assert "BRACKET_LEAK" in policy["findings"]
    assert out["votes"]["risk_judge"]["vote"] != "BLOCK"
    assert out["votes"]["faithfulness_judge"]["vote"] != "BLOCK"

    # NARR-3 attached the floor contracts (was 0 in NARR-1); NARR-4 demoted LENGTH_VIOLATION out
    # of the floor, leaving 2 pure-stdlib in_process floor contracts. They never reach :8002, and
    # on this complete-generation clean scene none fire.
    assert out["n_verification_contracts"] == 2
    assert out["healthcare_reads"] == [], f"healthcare leaked under pack=narrative: {out['healthcare_reads']}"
    assert out["build_judge_lm_callable"] is True

    # the rendered narrative judge prompts carry ZERO clinical needles (non-clinical domain)
    hits = {}
    for role, text in out["rendered"].items():
        found = sorted({m.lower() for m in CLINICAL_NEEDLES.findall(text)})
        if found:
            hits[role] = found
    assert not hits, f"clinical-needle leakage in the narrative judge prompts: {hits}"
