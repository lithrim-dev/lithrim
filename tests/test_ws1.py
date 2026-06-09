"""WS-1 offline acceptance: config-plane + ontology drive the WS-0 vertical.

No network, no Synthea CSV, no live call. Everything runs against the vendored
fixtures in tests/fixtures/ws0/ + the committed ontology / agent seeds. Covers
driver §5 A1–A3 (A4 = full-suite-green + ruff, checked at the suite level).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from lithrim_bench.harness import grounding
from lithrim_bench.harness.collections import COLLECTIONS, COMPLIANCE_REPORT
from lithrim_bench.harness.config import (
    Agent,
    Dataset,
    EvalProfile,
    load_agent,
    save_agent,
    seed_config_db,
)
from lithrim_bench.harness.ontology import load_ontology
from lithrim_bench.picklist import expected_block, normalize_expected_verdict

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "ws0"
CASE_ID = "bench_scribe_v1_inject_condition_1bd0f10dc7b5"
BASELINE = FIXTURES / f"baseline.{CASE_ID}.json"
CASE = FIXTURES / f"case.{CASE_ID}.jsonl"
ONTOLOGY_SEED = REPO_ROOT / "packs" / "healthcare" / "ontology.json"
HARNESS_DIR = REPO_ROOT / "lithrim_bench" / "harness"


def _agent_over_fixtures() -> Agent:
    return Agent(
        name="ws1_test",
        eval_profile=EvalProfile(
            judges=("risk_judge", "policy_judge", "faithfulness_judge"),
            council_config={"disposition": "compose-over-live-v2"},
            ontology_ref="clinical/1",
            ontology_path=str(ONTOLOGY_SEED),
            tools=("presence_check",),
            kb_bindings={},
            severity_map_ref="ontology:clinical/1",
        ),
        dataset=Dataset(case_id=CASE_ID, source=str(CASE), baseline=str(BASELINE)),
    )


# ── A1: the run is driven entirely from SQLite config ─────────────────────────


def test_config_roundtrip_through_sqlite(tmp_path):
    """A1 — an Agent eval-profile persists to and loads from the config SQLite."""
    db = tmp_path / "config.sqlite"
    save_agent(_agent_over_fixtures(), db_path=db)
    loaded = load_agent("ws1_test", db_path=db)
    assert loaded.dataset.case_id == CASE_ID
    assert loaded.eval_profile.ontology_ref == "clinical/1"
    # S-BS-6 stored (not injected) in council_config
    assert loaded.eval_profile.council_config["disposition"] == "compose-over-live-v2"


def test_seed_config_db_builds_committed_agent(tmp_path):
    """A1 — the committed agent seed builds into the config DB."""
    db = tmp_path / "config.sqlite"
    names = seed_config_db(db_path=db)
    assert "ws0_default" in names
    agent = load_agent("ws0_default", db_path=db)
    assert agent.eval_profile.tools == ("presence_check",)


def test_config_driven_run_reproduces_ws0(tmp_path):
    """A1 — run_eval, driven only by a config Agent, reproduces the WS-0 result.

    No --case/--baseline/contracts args: case, baseline, contracts, severity map and
    council disposition all come from the Agent + ontology.
    """
    db = tmp_path / "config.sqlite"
    save_agent(_agent_over_fixtures(), db_path=db)

    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "run_eval.py"),
            "--agent",
            "ws1_test",
            "--config-db",
            str(db),
            "--out-dir",
            str(tmp_path / "out"),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, proc.stderr
    assert "verdict: reject" in proc.stdout
    assert "MEDICATION_NOT_IN_TRANSCRIPT -> SUPPRESSED" in proc.stdout
    assert "ECE:" in proc.stdout


# ── A2: the ontology is the single source ─────────────────────────────────────


def test_ontology_is_single_source_for_contracts_and_severity():
    """A2 — flags/tiers/owners/contracts/severity come from the ontology seed."""
    ont = load_ontology(ONTOLOGY_SEED)
    assert ont.ontology_version == "clinical/1"
    assert len(ont.flags) == 23  # CITATION-DRIFT: driver said 24; actual is 23

    # the med presence-check is present AS A DECLARATION with explicit params (Q4.3)
    decl = ont.contract_for("MEDICATION_NOT_IN_TRANSCRIPT")
    assert decl is not None
    assert decl.contract_type == "presence_check"
    assert decl.params["med_source"] == "patient_profile.active_medications"
    assert decl.params["token_min_len"] == 4
    assert "tablet" in decl.params["noise_tokens"]

    # severity map is data (Q4.2): a lone MEDIUM blocks
    assert ont.severity_map.rescore([{"severity": "MEDIUM"}]) == "BLOCK"
    assert ont.severity_map.rescore([{"severity": "LOW"}]) == "WARN"
    assert ont.severity_map.rescore([]) == "PASS"


def test_no_hardcoded_constants_remain_in_harness():
    """A2 — the WS-0 sentinels are gone from the harness source."""
    grounding_src = (HARNESS_DIR / "grounding.py").read_text()
    assert "WS0_CONTRACTS" not in grounding_src
    assert "SEVERITY_WEIGHT" not in grounding_src
    correction_src = (HARNESS_DIR / "correction.py").read_text()
    assert "ws0-hardcoded/0" not in correction_src


def test_presence_check_honours_declared_params(tmp_path):
    """A2/Q4.3 — the extraction strategy is driven by the contract's params.

    A token_min_len of 6 must drop the 4-char salvageable token, so a med whose only
    distinguishing token is shorter than the floor cannot be matched — proving the
    floor is read from the declaration, not a module constant.
    """
    ont = load_ontology(ONTOLOGY_SEED)
    decl = ont.contract_for("MEDICATION_NOT_IN_TRANSCRIPT")

    base = grounding.PresenceCheck(decl)
    case = {
        "transcript": "patient takes asss daily",
        "patient_profile": {"active_medications": ["asss 50 mg"]},
    }
    # 'asss' is 4 chars — matches at the default floor of 4
    assert base.check({}, case).disproved is True

    raised = dict(decl.params, token_min_len=6)
    from lithrim_bench.harness.ontology import VerificationContractDecl

    strict = grounding.PresenceCheck(
        VerificationContractDecl(
            flag_code=decl.flag_code,
            question=decl.question,
            contract_type=decl.contract_type,
            params=raised,
            version=decl.version,
        )
    )
    # with a 6-char floor, 'asss' is below the floor → no match → not disproved
    assert strict.check({}, case).disproved is False


def test_correction_records_owner_roles_and_real_version():
    """A2/Q4.1 — correction record carries the real ontology version + owner_roles."""
    from lithrim_bench.harness.correction import build_correction

    baseline = json.loads(BASELINE.read_text())
    case = json.loads(CASE.read_text().splitlines()[0])
    grounded = grounding.ground(baseline, case)
    rec = build_correction(
        suppressed_entry=grounded.suppressed[0],
        result=baseline,
        composite_before=grounded.original_verdict,
        composite_after=grounded.verdict,
    )
    assert rec["ontology_version"] == "clinical/1"
    # MEDICATION_NOT_IN_TRANSCRIPT is Tier-2 with no _TIER1_OWNERS entry → []
    assert rec["owner_roles"] == []


# ── A3: doc-shim collections + recorded rationale ─────────────────────────────


def test_doc_shim_collections_roundtrip(tmp_path):
    """A3 — the 4 doc-shim collections create/insert/get/find_by_fk round-trip."""
    db = tmp_path / "collections.sqlite"
    names = {c.name for c in COLLECTIONS}
    assert names == {"conversation_item", "conversation_session", "call_kpi", "compliance_report"}

    COMPLIANCE_REPORT.insert(
        {"report_id": "r1", "case_id": CASE_ID, "verdict": "reject"}, db_path=db
    )
    COMPLIANCE_REPORT.insert(  # idempotent upsert on id
        {"report_id": "r1", "case_id": CASE_ID, "verdict": "needs_review"}, db_path=db
    )
    assert COMPLIANCE_REPORT.get("r1", db_path=db)["verdict"] == "needs_review"
    by_case = COMPLIANCE_REPORT.find_by_fk(CASE_ID, db_path=db)
    assert len(by_case) == 1


def test_doc_shim_rationale_recorded():
    """A3 — the doc-shim-vs-relational rationale is recorded in the module docstring."""
    import lithrim_bench.harness.collections as coll

    doc = coll.__doc__ or ""
    assert "doc-shim" in doc.lower()
    assert "relational" in doc.lower()


# ── S-BS-9 normalization ──────────────────────────────────────────────────────


def test_expected_verdict_shape_contract():
    """S-BS-9 — both shapes normalize; expected_block tolerates either."""
    assert normalize_expected_verdict("reject") == {"reject"}
    assert normalize_expected_verdict(["needs_review", "reject"]) == {"needs_review", "reject"}
    assert expected_block({"expected_compliance_verdict": "reject"}) is True
    assert expected_block({"expected_compliance_verdict": ["needs_review", "reject"]}) is True
    assert expected_block({"expected_compliance_verdict": ["approve"]}) is False


# ── S-BS-58 ontology cache busts on a draft edit ──────────────────────────────


def test_load_ontology_busts_cache_when_the_draft_changes(tmp_path):
    """S-BS-58 — load_ontology is keyed on (path, mtime), so editing a draft and
    reloading the SAME path reflects the edit. The original @lru_cache(path) cached by
    path alone, so a long-running process (the BFF) silently reused the stale ontology
    on the 2nd+ edit of a draft — breaking iterative 'edit the flag → see it grade'.
    The A2 test only covered committed→draft (distinct paths); this covers
    draft→edit-same-draft (one path)."""
    import os

    base = json.loads(ONTOLOGY_SEED.read_text())
    draft = tmp_path / "draft.json"

    base["severity_map"]["block_at_or_above"] = 0.5
    draft.write_text(json.dumps(base))
    assert load_ontology(draft).severity_map.block_at_or_above == 0.5

    base["severity_map"]["block_at_or_above"] = 99.0
    draft.write_text(json.dumps(base))
    st = draft.stat()  # force a later mtime so the bust is deterministic on any FS
    os.utime(draft, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))

    assert load_ontology(draft).severity_map.block_at_or_above == 99.0
