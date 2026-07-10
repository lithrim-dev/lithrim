"""CE-STANDALONE-1 — the headless standalone walking-skeleton (the demonstrable generic-CE proof).

Proves the OSS Core runs STANDALONE as a domain-agnostic eval engine: a genuinely
INDEPENDENT non-clinical pack (``packs/support_ticket_qa/`` — its OWN ontology + council_roles
+ taxonomy, ZERO ``packs/healthcare/`` paths, unlike ``story_audit`` which reuses healthcare's)
grades a non-clinical case through the AUTHORED path (``render_role_questions`` → ``build_trio``
→ withstands-gate → frozen ``_apply_consensus`` → composite verdict) with the healthcare pack
UNLOADED and ``:8002`` DOWN, at $0 via injected mock predictors.

This is the FALSIFICATION of the decoupling claim (SPEC_STANDALONE_CORE_VALIDATION §1/§5):
PACK-2c swapped a pack's DATA but every non-healthcare pack still reused healthcare's PROMPTS +
ontology. Here the domain content is genuinely absent. Honest-Δ: if any leg fails it pinpoints
a residual coupling — that is the point of the test (§5).

Structure mirrors ``tests/test_pack_layer2c.py``: module-level pack resolution is import-frozen
(``judge_assignment.py`` ``_ROLE_PROMPTS_DIR = pack_prompts_path()``; ``judge_metric.LENS_BY_ROLE``),
so the pack swap MUST run in a subprocess with ``LITHRIM_BENCH_PACK=support_ticket_qa``. The CI
grade is $0 (injected predictors, the ``test_uap3_grade`` pattern) — the real-provider confirmation
is a separately-gated live smoke, never CI spend.

Findings surfaced by this cycle (both residual couplings for "standalone CE"; NEITHER blocks the
pack from running, so this is a finding, not an escalation):
  * S-BS-129 — the core DSPy ``JudgeSignature`` hard-codes clinical prose (see the non-gating
    diagnostic below). Off the authored render path; the $0 predictor path bypasses it.
  * S-BS-130 — CLOSED by CE-PACK-NEUTRAL-DEFAULT. ``DEFAULT_PACK`` used to be ``'healthcare'``,
    making ``council_roster()`` read healthcare's ``pack.json`` + ``taxonomy_snapshot.json`` for
    canonical-roster validation even under a non-healthcare active pack. The default is now the
    neutral ``_core`` pack, so A-STANDALONE-4 tightened to assert ZERO ``packs/healthcare/`` reads
    (see ``tests/test_neutral_default.py`` for the env-unset shipped-default proof).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

# build_authored_semantic_stage → build_trio (dspy) + ComplianceCouncil (openai). The render +
# source-grep legs are light, but the grade legs need the [council] extra; gate the whole file on
# it (run in debuglithrim), matching test_uap3_grade.
pytest.importorskip("openai")
pytest.importorskip("dspy")

REPO_ROOT = Path(__file__).resolve().parents[1]
PACK = "support_ticket_qa"
MARKER = "=== AUTHORED REFINEMENT (ontology assignment) ==="

# The SPEC §2.1 clinical needles — inverted-green here (we assert ZERO hits in the rendered
# non-clinical judge prompts).
CLINICAL_NEEDLES = re.compile(
    r"HIPAA|patient|medication|dosage|allerg|clinical|SOAP|escalat|consent|transcript",
    re.IGNORECASE,
)


def _run_subprocess(script: str, pack: str) -> dict:
    """Run ``script`` in a fresh interpreter under ``LITHRIM_BENCH_PACK=pack`` and parse the
    single ``__JSON__``-prefixed payload line it prints. A subprocess because pack resolution is
    frozen at module import (so the active pack cannot be swapped in-process)."""
    import os

    env = dict(os.environ)
    env["LITHRIM_BENCH_PACK"] = pack
    # S-BS-139: make the grade subprocess hermetic. The FROZEN ComplianceCouncil builds an OpenAI
    # client *object* at construction (no network), which needs a key + an openai provider. setdefault
    # (not assignment) so a real live-smoke env still wins; this stops the subprocess from depending
    # on the council conftest's leaked defaults / suite order / a repo-root ``.env``.
    env.setdefault("OPENAI_API_KEY", "test-offline-key")
    env.setdefault("LITHRIM_LLM_PROVIDER", "openai")
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"standalone subprocess failed under pack={pack!r}:\n"
        f"--- STDOUT ---\n{proc.stdout}\n--- STDERR ---\n{proc.stderr}"
    )
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("__JSON__")), None)
    assert line is not None, f"no __JSON__ payload:\n{proc.stdout}\n{proc.stderr}"
    return json.loads(line[len("__JSON__") :])


# ── the two subprocess bodies ───────────────────────────────────────────────

_RENDER_SCRIPT = r"""
import json
from lithrim_bench.harness.pack import (
    active_pack,
    pack_lenses,
    pack_ontology_path,
    pack_production_judges,
    pack_prompts_path,
)
from lithrim_bench.harness.ontology import load_ontology
from lithrim_bench.runtime.council.judge_assignment import render_role_questions

ont = load_ontology(pack_ontology_path())
lenses = pack_lenses()
out = {
    "active_pack": active_pack(),
    "prompts_dir": str(pack_prompts_path()),
    "ontology_path": str(pack_ontology_path()),
    "rendered": {},
}
for role in pack_production_judges():
    out["rendered"][role] = {
        "base": render_role_questions(ont, role),
        "authored": render_role_questions(
            ont, role, assigned_flags=sorted(lenses.get(role, []))
        ),
    }
print("__JSON__" + json.dumps(out))
"""

_GRADE_SCRIPT = r"""
import json
import sys

# A-STANDALONE-4: an audit hook records every file OPENED during the grade, so we can prove no
# healthcare DOMAIN file is read at runtime (only the hardcoded DEFAULT_PACK roster metadata).
_opened = []


def _audit(event, args):
    if event == "open" and args and isinstance(args[0], (str, bytes)):
        p = args[0].decode() if isinstance(args[0], bytes) else args[0]
        _opened.append(p)


sys.addaudithook(_audit)

from lithrim_bench.harness.pack import active_pack, pack_ontology_path, pack_prompts_path
from lithrim_bench.harness.ontology import load_ontology
from lithrim_bench.harness.grade import grade_inprocess
from lithrim_bench.harness.grounding import ground
from lithrim_bench.harness.report import composite
from lithrim_bench.picklist import load_case
from lithrim_bench.runtime.council.authored_stage import build_authored_semantic_stage
from lithrim_bench.runtime.council.judges_dspy import V2_ROLES, build_judge_lm

CASE_ID = "support_ticket_qa_fabricated_policy"
CASE_SRC = "tests/fixtures/standalone/case.support_ticket_qa_fabricated_policy.jsonl"
ROLE = "policy_judge"
FLAG = "FABRICATED_POLICY"
MARKER = "=== AUTHORED REFINEMENT (ontology assignment) ==="

ont = load_ontology(pack_ontology_path())
case = load_case(CASE_ID, source=CASE_SRC)
assert case is not None, "case did not load"


def _predictor(role):
    # $0/offline: BLOCK with FLAG iff this judge carries the authored refinement (the same
    # marker-keyed predictor as test_uap3_grade) — so the FLIP is the authoring, not the case.
    def _p(*, role_key_questions="", **_kw):
        if role == ROLE and MARKER in role_key_questions:
            return {
                "decision": "reject",
                "findings": [{
                    "taxonomy_code": FLAG,
                    "evidence_spans": [{"quote": "guaranteed-refund policy", "turn_ids": []}],
                }],
            }
        return {"decision": "approve", "findings": []}

    return _p


stage = build_authored_semantic_stage(
    ontology=ont,
    assignments={ROLE: [FLAG]},
    predictors={r: _predictor(r) for r in V2_ROLES},
)
r = grade_inprocess(case, semantic_stage=stage)
comp = composite(ground(r, case, ontology=ont))

votes = {
    v["judge_role"]: {"vote": v["vote"], "findings": list(v.get("findings") or [])}
    for v in r["semantic"]["judge_votes"]
}


def _norm(p):
    return p.replace("\\", "/")


healthcare_reads = sorted({_norm(p) for p in _opened if "packs/healthcare" in _norm(p)})

print("__JSON__" + json.dumps({
    "active_pack": active_pack(),
    "prompts_dir": _norm(str(pack_prompts_path())),
    "ontology_path": _norm(str(pack_ontology_path())),
    "n_verification_contracts": len(ont.contracts),
    "verdict": comp["verdict"],
    "votes": votes,
    "healthcare_reads": healthcare_reads,
    "build_judge_lm_callable": callable(build_judge_lm),
}))
"""


@pytest.fixture(scope="module")
def grade_out():
    """The $0 authored-path E2E, run once (subprocess), shared by A-STANDALONE-2..5."""
    return _run_subprocess(_GRADE_SCRIPT, PACK)


# ── A-STANDALONE-1: 0 clinical leakage in the authored judge prompts ─────────


def test_a1_zero_clinical_leakage_in_authored_prompts():
    """A1: under the generic pack, every production judge's rendered prompt (seed base AND the
    authored-refinement variant) has ZERO clinical-needle hits — the SPEC §2.1 grep, green."""
    out = _run_subprocess(_RENDER_SCRIPT, PACK)
    assert out["active_pack"] == PACK
    assert f"/packs/{PACK}/" in out["prompts_dir"]
    hits = {}
    for role, variants in out["rendered"].items():
        for variant, text in variants.items():
            found = sorted({m.lower() for m in CLINICAL_NEEDLES.findall(text)})
            if found:
                hits[f"{role}.{variant}"] = found
    assert not hits, f"clinical-needle leakage in the authored judge prompts: {hits}"
    # non-vacuity: the authored refinement actually rendered (else we'd grep near-empty text)
    for role, variants in out["rendered"].items():
        assert MARKER in variants["authored"], f"{role}: no authored refinement rendered"
        assert "JUDGE" in variants["base"].upper(), f"{role}: base role prompt missing"


# ── A-STANDALONE-2: the authored path grades end-to-end to a verdict ─────────


def test_a2_authored_path_grades_to_a_verdict(grade_out):
    """A2: the non-clinical case grades through the authored path to a verdict. Assigning
    FABRICATED_POLICY to its owner (policy_judge) → that judge BLOCKs → Tier-1 one-strike →
    composite reject. The unassigned roles do not block, so the move is the AUTHORING."""
    assert grade_out["verdict"] == "reject"
    policy = grade_out["votes"]["policy_judge"]
    assert policy["vote"] == "BLOCK"
    assert "FABRICATED_POLICY" in policy["findings"]
    assert grade_out["votes"]["risk_judge"]["vote"] != "BLOCK"
    assert grade_out["votes"]["faithfulness_judge"]["vote"] != "BLOCK"


# ── A-STANDALONE-3: :8002 down does not crash the grade ──────────────────────


def test_a3_grade_completes_with_8002_down(grade_out):
    """A3: the generic ontology declares NO verification_contracts, so signals/grounding run no
    contract executor and never reach :8002 (which is down in CI). The grade still completes and
    returns a verdict — no crash, no silent clear."""
    assert grade_out["n_verification_contracts"] == 0
    assert grade_out["verdict"] == "reject"


# ── A-STANDALONE-4: healthcare unloaded — the active domain is 100% the generic pack ─────


def test_a4_healthcare_domain_unloaded(grade_out):
    """A4: the run resolves its ENTIRE active domain from the generic pack and reads ZERO
    ``packs/healthcare/`` files — neither domain content (ontology/council_roles/floors) NOR the
    canonical-roster metadata.

    Post CE-PACK-NEUTRAL-DEFAULT the core-shipped ``DEFAULT_PACK`` is the neutral ``_core`` pack,
    so ``council_roster()`` reads ``packs/_core/`` for the canonical roster — the two healthcare
    metadata files it used to read under ``DEFAULT_PACK='healthcare'`` are gone. This is the strict
    form of the gate, now achievable: **S-BS-130 closed.**

    Non-vacuous: the audit hook records EVERY ``packs/healthcare/`` open across boot+grade, so the
    same run under ``LITHRIM_BENCH_PACK=healthcare`` (the suite's pinned default) populates
    ``healthcare_reads`` — support_ticket_qa reading ZERO is therefore a genuine decouple signal."""
    assert grade_out["active_pack"] == PACK
    assert f"/packs/{PACK}/" in grade_out["prompts_dir"]
    assert f"/packs/{PACK}/" in grade_out["ontology_path"]

    reads = grade_out["healthcare_reads"]
    # ZERO healthcare reads — the strict gate, now achievable. Post CE-PACK-NEUTRAL-DEFAULT the
    # core-shipped DEFAULT_PACK is the neutral ``_core`` pack, so ``council_roster()`` reads
    # ``packs/_core/`` (not healthcare) for the canonical roster metadata. S-BS-130 (which left
    # ``pack.json`` + ``taxonomy_snapshot.json`` leaking under the old healthcare default) is closed:
    # the run reads NO ``packs/healthcare/`` file at all — neither domain content nor roster metadata.
    assert not reads, (
        f"healthcare read under a non-healthcare active pack (S-BS-130 not closed): {reads}"
    )


# ── A-STANDALONE-5: the BYO provider seam ────────────────────────────────────


def test_a5_provider_seam_present_and_bypassed_at_zero_cost(grade_out):
    """A5: the BYO provider seam (``build_judge_lm``) exists; the $0 CI path binds injected
    predictors INSTEAD of a live LM, so no provider is constructed and no spend occurs. The
    real-provider confirmation is the separately-gated live smoke (not run in CI)."""
    assert grade_out["build_judge_lm_callable"] is True


# ── S-BS-129 / G4 CLOSED: the core judge signature is clinical-clean (CE-PACK-6b-CLEAN) ──


def test_core_judge_signature_is_clinical_clean():
    """S-BS-129 / G4 CLOSED (CE-PACK-6b-CLEAN). The core DSPy ``JudgeSignature``
    (``judges_dspy.py`` ``_build_signature``) was genericized to a domain-agnostic scaffold, so
    even the LIVE path sends NO clinical prose to the LLM — domain specificity now arrives ONLY
    via ``role_key_questions`` (pack role prompts) + ``taxonomy_context`` (pack codes). This was
    the non-gating S-BS-129 tracker (it used to assert the residue was PRESENT); it is now
    INVERTED to assert the residue is GONE. ``transcript`` survives only as a generic I/O field
    NAME (not a clinical needle for the demarcation grep). SPEC_STANDALONE_CORE_VALIDATION §3.3."""
    src = (REPO_ROOT / "lithrim_bench/runtime/council/judges_dspy.py").read_text()
    start = src.index("def _build_signature")
    end = src.index("return JudgeSignature", start)
    needles = sorted({m.lower() for m in CLINICAL_NEEDLES.findall(src[start:end])})
    clinical = set(needles) - {"transcript"}  # the generic field NAME, kept by design (§1.1)
    assert not clinical, (
        f"_build_signature must be clinical-clean after 6b-CLEAN (S-BS-129/G4); found: {sorted(clinical)}"
    )
