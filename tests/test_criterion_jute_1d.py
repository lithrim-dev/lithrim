"""CRITERION-JUTE-1d — the orchestration endpoint that ties the CRITERION-JUTE stack together:
an SME picks a tool+call, a plain-English criterion seeds generation (1b), the bidirectional
corpus gate runs (1c), the gate report renders inline, and the ``mcp_call`` + ``arguments_jute``
contract PINS on pass (1a's ``_pin_arguments_jute``). This proves the BFF endpoint
``POST /v1/criterion-jute/generate``:

  D1a — PREVIEW (commit=False): returns the generated ``arguments_jute`` + its sha256 + the
        gate report, and writes NOTHING (no contract lands in verification_contracts).
  D1b — COMMIT + gate-pass: pins ONE mcp_call contract whose stored params carry BOTH
        ``arguments_jute`` AND ``arguments_jute_sha256`` (1a), audited.
  D1c — COMMIT + gate-FAIL: 422 naming the failing case_ids, and writes NO contract.

The endpoint's generate + gate seams are INJECTABLE (module-level hooks the tests monkeypatch),
so this runs networkless (no :3031, no LM, no Hermes). The gate seam here reuses the REAL 1c
``gate_contract_over_corpus`` with the golden fakes from ``tests/test_criterion_jute_1c`` so the
gate is genuinely exercised, not stubbed. Mirrors ``tests/test_eval_flow.py``'s ``env`` fixture
(the [bff] extra, a tmp config plane + ontology workdir, a TestClient over the SAME db/workdir).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from lithrim_bench.harness.config import Agent, Dataset, EvalProfile, save_agent

REPO_ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_SEED = REPO_ROOT / "packs" / "healthcare" / "ontology.json"

_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

AGENT = "cjute1d_test"
# a REAL in-ontology healthcare flag (the pin path requires a known flag; an unknown one 404s).
KNOWN_FLAG = "UPCODING_RISK"

# reuse the 1c golden fixtures so the injected gate is the REAL 1c gate, not a stub.
from lithrim_bench.verification.argshape_gate import (  # noqa: E402
    gate_contract_over_corpus,
)
from tests.test_criterion_jute_1c import (  # noqa: E402
    GOLDEN_ARGUMENTS_JUTE,
    build_snomed_oracle,
    golden_jute_apply,
    wrong_direction_jute_apply,
)

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "subsumption_bidirectional"


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _corpus_parts():
    positives = _load_jsonl(FIXTURES / "upcoded_positives.jsonl")
    negatives = _load_jsonl(FIXTURES / "clean_generalization_negatives.jsonl")
    span_bind = _load_jsonl(FIXTURES / "span_bind_positives.jsonl")
    return positives, negatives, span_bind


def _pack_ontology_abspath() -> Path:
    """The DISCOVERED active-pack ontology (the same self-heal the BFF applies when the in-repo seed
    is absent post-PACK-DIST). Used to build the hermetic clean draft in the fixture."""
    from lithrim_bench.harness import pack as _pack_mod

    return Path(_pack_mod.pack_ontology_path(_pack_mod.active_pack()))


def _fixture_agent() -> Agent:
    return Agent(
        name=AGENT,
        eval_profile=EvalProfile(
            judges=("risk_judge",),
            council_config={},
            ontology_ref="clinical/1",
            ontology_path=str(ONTOLOGY_SEED),
            tools=(),
            kb_bindings={},
            severity_map_ref="ontology:clinical/1",
        ),
        dataset=Dataset(case_id="c", source="s", baseline="b"),
    )


@pytest.fixture
def env(tmp_path, monkeypatch):
    pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")
    import app as bff
    from fastapi.testclient import TestClient

    from lithrim_bench.harness import workspace as _workspace
    from lithrim_bench.harness.pack import active_pack

    monkeypatch.setattr(
        _workspace,
        "get_active_workspace",
        lambda: _workspace.Workspace(name="default", pack=active_pack()),
    )

    db = tmp_path / "bench_config.sqlite"
    workdir = tmp_path / "ont"
    workdir.mkdir(parents=True, exist_ok=True)
    examples = tmp_path / "examples"
    examples.mkdir()
    save_agent(_fixture_agent(), db_path=db)

    # HERMETIC: seed a clean DRAFT ontology (workdir/{agent}.json — _resolve_ontology_path prefers
    # it) whose gradeable flags are ALL snapshot-admissible, so the FROZEN put_ontology_endpoint's
    # snapshot lint validates the whole ontology cleanly. This isolates the test from the pack
    # working-tree's own drift (the "23-vs-25" open condition: the pack ontology may carry a
    # gradeable flag not yet in the snapshot, which would false-reject ANY unrelated PUT). The pin
    # target (UPCODING_RISK) survives the filter.
    from lithrim_bench.harness import pack as _pack_mod

    admissible = set(_pack_mod.pack_taxonomy_codes(active_pack()))
    seed = json.loads(_pack_ontology_abspath().read_text())
    seed["flags"] = [
        f for f in seed.get("flags", [])
        if (not f.get("gradeable")) or f.get("flag") in admissible
    ]
    seed["verification_contracts"] = []
    (workdir / f"{AGENT}.json").write_text(json.dumps(seed))

    bff.app.dependency_overrides[bff.get_config_db] = lambda: db
    bff.app.dependency_overrides[bff.get_ontology_workdir] = lambda: workdir
    bff.app.dependency_overrides[bff.get_examples_dir] = lambda: examples
    try:
        yield bff, TestClient(bff.app), db, workdir
    finally:
        bff.app.dependency_overrides.clear()


def _draft_contracts(workdir: Path, agent: str = AGENT):
    draft = workdir / f"{agent}.json"
    if not draft.exists():
        return []
    return json.loads(draft.read_text()).get("verification_contracts") or []


# --------------------------------------------------------------------------- #
# the injected seams: a FIXED generator + the REAL 1c gate over the golden fakes
# --------------------------------------------------------------------------- #
def _install_seams(bff, *, jute_apply, arguments_jute=GOLDEN_ARGUMENTS_JUTE, monkeypatch):
    """Wire the endpoint's generate + gate hooks. The generator returns a FIXED arguments_jute +
    its sha256 (no LM / no :3031). The gate runs the REAL 1c ``gate_contract_over_corpus`` over the
    golden corpus with the caller's ``jute_apply`` (golden -> pass; wrong-direction -> fail) and the
    disclosed-circularity oracle. So the endpoint's orchestration is exercised end-to-end offline."""
    positives, negatives, span_bind = _corpus_parts()
    corpus = [*positives, *negatives, *span_bind]
    oracle = build_snomed_oracle(positives, negatives, span_bind)
    sha = hashlib.sha256(arguments_jute.encode("utf-8")).hexdigest()

    def fake_generate(*, flag_code, tool, call, criterion, sample_case, input_schema, n_generations):
        return {"arguments_jute": arguments_jute, "arguments_jute_sha256": sha}

    def fake_gate(candidate_params):
        return gate_contract_over_corpus(
            candidate_params, corpus, jute_apply=jute_apply, snomed_oracle=oracle
        )

    monkeypatch.setattr(bff, "_criterion_jute_generate_argshape", fake_generate)
    monkeypatch.setattr(bff, "_criterion_jute_gate", fake_gate)
    return sha


# --------------------------------------------------------------------------- #
# D1a — PREVIEW returns arguments_jute + gate_report, writes NOTHING
# --------------------------------------------------------------------------- #
def test_preview_returns_argshape_and_gate_report_no_write(env, monkeypatch):
    bff, client, db, workdir = env
    sha = _install_seams(bff, jute_apply=golden_jute_apply, monkeypatch=monkeypatch)

    r = client.post(
        "/v1/criterion-jute/generate",
        json={
            "flag_code": KNOWN_FLAG,
            "tool": "gate_snomed_subsumption",
            "call": "subsumed_by",
            "criterion": "The note diagnosis must not be more specific than the record supports.",
            "commit": False,
            "agent": AGENT,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "preview"
    assert body["arguments_jute"] == GOLDEN_ARGUMENTS_JUTE
    assert body["arguments_jute_sha256"] == sha
    gr = body["gate_report"]
    assert gr["passed"] is True
    assert gr["negatives_cleared"] == gr["negatives_total"] == 22
    assert gr["positives_standing"] == gr["positives_total"] == 24
    assert gr["span_bind_ok"] == gr["span_bind_cases"] == 2
    assert gr["failures"] == []
    # NOTHING persisted — a preview is $0 and writes no contract.
    assert _draft_contracts(workdir) == []


# --------------------------------------------------------------------------- #
# D1b — COMMIT + gate-pass pins ONE mcp_call contract carrying jute + sha256
# --------------------------------------------------------------------------- #
def test_commit_gate_pass_pins_contract_with_jute_and_sha(env, monkeypatch):
    bff, client, db, workdir = env
    sha = _install_seams(bff, jute_apply=golden_jute_apply, monkeypatch=monkeypatch)

    r = client.post(
        "/v1/criterion-jute/generate",
        json={
            "flag_code": KNOWN_FLAG,
            "tool": "gate_snomed_subsumption",
            "call": "subsumed_by",
            "criterion": "record-vs-note subsumption",
            "commit": True,
            "agent": AGENT,
            "rationale": "pin the corpus-gated arg-shaping transform",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "pinned"
    assert body["gate_report"]["passed"] is True

    contracts = _draft_contracts(workdir)
    mine = [c for c in contracts if c.get("flag_code") == KNOWN_FLAG]
    assert len(mine) == 1, contracts
    c = mine[0]
    assert c["contract_type"] == "mcp_call"
    p = c["params"]
    assert p["tool"] == "gate_snomed_subsumption"
    assert p["call"] == "subsumed_by"
    # the stored params carry BOTH the pinned transform AND its sha256 (1a).
    assert p["arguments_jute"] == GOLDEN_ARGUMENTS_JUTE
    assert p["arguments_jute_sha256"] == sha

    # the write is AUDITED (an action=edit / target=ontology record fires through put_ontology).
    audit = client.get("/v1/audit", params={"target_type": "ontology"})
    assert audit.status_code == 200
    records = audit.json().get("records") or audit.json().get("audit") or []
    assert records, audit.json()


# --------------------------------------------------------------------------- #
# D1c — COMMIT + gate-FAIL returns 422 (naming case_ids), writes NO contract
# --------------------------------------------------------------------------- #
def test_commit_gate_fail_422_and_no_write(env, monkeypatch):
    bff, client, db, workdir = env
    # the WRONG-DIRECTION jute_apply makes the corpus gate FAIL (negatives stand + positives clear).
    _install_seams(bff, jute_apply=wrong_direction_jute_apply, monkeypatch=monkeypatch)

    r = client.post(
        "/v1/criterion-jute/generate",
        json={
            "flag_code": KNOWN_FLAG,
            "tool": "gate_snomed_subsumption",
            "call": "subsumed_by",
            "criterion": "record-vs-note subsumption",
            "commit": True,
            "agent": AGENT,
        },
    )
    assert r.status_code == 422, r.text
    detail = json.dumps(r.json())
    # the 422 names failing case ids (a clean-generalization negative that stood).
    positives, negatives, _ = _corpus_parts()
    a_failing_negative = negatives[0]["case_id"]
    assert a_failing_negative in detail
    # NO contract persisted on a failed gate.
    assert all(c.get("flag_code") != KNOWN_FLAG for c in _draft_contracts(workdir))


def test_commit_unknown_flag_404_no_write(env, monkeypatch):
    """The pin path reuses the FROZEN put path, so an unknown flag 404s (nothing persisted)."""
    bff, client, db, workdir = env
    _install_seams(bff, jute_apply=golden_jute_apply, monkeypatch=monkeypatch)
    r = client.post(
        "/v1/criterion-jute/generate",
        json={
            "flag_code": "NOPE_NOT_A_FLAG",
            "tool": "gate_snomed_subsumption",
            "call": "subsumed_by",
            "criterion": "x",
            "commit": True,
            "agent": AGENT,
        },
    )
    assert r.status_code == 404, r.text
    assert _draft_contracts(workdir) == []
