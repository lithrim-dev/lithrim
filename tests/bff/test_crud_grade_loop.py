"""CRUD-2 (loop-lock) — the create→assign→grade loop, end-to-end + $0.

This LOCKS the BFF half of the authored-config → grade loop with a deterministic
contract: an audited ``PUT /v1/judges/{role}`` persists the authored lens (and the
BYOK model selector); a subsequent ``POST /v1/run-eval`` reads that persisted
``JudgeConfig`` and THREADS it into ``run_eval.run(assignments=, models=)``. The
council-consumes-it half (``build_trio(assignments=/models=)``) is already proven
by green tests, CITED here, not duplicated:

  A1b — the rendered judge prompt reflects the authored lens:
        ``lithrim_bench/runtime/council/tests/test_judge_bridge.py
          ::test_build_trio_assignment_feeds_role_key_questions``
  A2b — ``build_trio(models={role: "byo-claude"})`` binds ``ClaudeCliLM``:
        ``tests/test_byoc_provider.py
          ::test_build_trio_models_assembles_a_mixed_provider_council``

The grade call (``run_eval.run``) is SPIED, so the assertions are $0 — no real
council fires (the live BYOK grade is already attested,
``docs/research/PROOF_byok_openai_council_2026-06-23.md``). The loop's
ignored-on-replay/live wrinkle (``scripts/run_eval.py`` docstring) is why this
gates the ``in_process`` path: only there are ``assignments``/``models`` consumed.

The ``assigned_flags`` are derived from the ACTIVE pack's lens at runtime
(``_active_lens_by_role``) rather than hardcoded, so the test passes the
owner↔emit PUT gate identically on the neutral ``_core`` default (bare CE) and on
a domain pack (dev/CI), and carries zero pack-specific (clinical) codes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
_SCRIPTS = REPO_ROOT / "scripts"
for _p in (_SCRIPTS, _BFF):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


@pytest.fixture
def bff_client(tmp_path, monkeypatch):
    """A hermetic BFF TestClient over a temp config DB, routing run-eval IN-PROCESS
    on the neutral ``_core`` default — the same seam ``tests/test_byoc_provider.py``
    uses. ``run_eval.run`` is spied per test, so no real grade fires ($0)."""
    pytest.importorskip("fastapi", reason="needs the [bff] extra")
    import app as bff
    from fastapi.testclient import TestClient

    from lithrim_bench.harness.config import save_agent
    from tests._house_fixture import house_agent

    # Process-global active-workspace pointer → pin the neutral _core default so run-eval
    # routes in-process (not a subprocess), regardless of any on-disk .active a local shell
    # left non-default. The PUT gate's owner↔emit lens reads this SAME active pack.
    monkeypatch.setattr(
        bff.workspace,
        "get_active_workspace",
        lambda: bff.workspace.Workspace(name="default", pack=bff.workspace.DEFAULT_PACK),
    )

    agent = house_agent(name="crud2_loop_test")
    db = tmp_path / "config.sqlite"
    save_agent(agent, db_path=db)
    bff.app.dependency_overrides[bff.get_config_db] = lambda: db
    bff.app.dependency_overrides[bff.get_out_dir] = lambda: tmp_path / "out"
    bff.app.dependency_overrides[bff.get_ontology_workdir] = lambda: tmp_path / "ont"
    bff.app.dependency_overrides[bff.get_collections_db] = lambda: tmp_path / "coll.sqlite"
    try:
        yield TestClient(bff.app), bff
    finally:
        bff.app.dependency_overrides.clear()


def _lens_subset(bff, role: str, n: int = 1) -> list[str]:
    """A non-empty ``assigned_flags`` subset for ``role`` drawn from the ACTIVE pack's
    owner↔emit lens — so the PUT passes the gate on whatever pack is active, with no
    hardcoded (pack-specific) codes."""
    lens = sorted(bff._active_lens_by_role().get(role, []))
    assert lens, f"the active pack offers no lens for {role!r}"
    return lens[:n]


# ── A1a: the authored LENS travels PUT /v1/judges -> POST /v1/run-eval (the grade) ──────


def test_authored_lens_threads_from_put_judge_to_the_grade(bff_client, monkeypatch):
    """A1a — the create→assign→grade loop, lens leg. An audited ``PUT /v1/judges/risk_judge``
    persists a chosen ``assigned_flags`` subset; the subsequent ``POST /v1/run-eval`` reads
    that persisted ``JudgeConfig`` and threads ``assignments={'risk_judge': <flags>}`` into
    ``run_eval.run`` (the authored lens reaches the in-process council). ``run_eval.run`` is
    spied so the grade is $0."""
    client, bff = bff_client
    authored = _lens_subset(bff, "risk_judge", n=1)

    put = client.put(
        "/v1/judges/risk_judge",
        json={"model": "", "assigned_flags": authored, "validator_refs": []},
    )
    assert put.status_code == 200, put.text

    captured: dict = {}

    def spy_run(agent, **kwargs):
        captured["assignments"] = kwargs.get("assignments")
        raise SystemExit("stop after capturing the threaded assignments")

    monkeypatch.setattr(bff.run_eval, "run", spy_run)
    resp = client.post("/v1/run-eval", json={"agent": "crud2_loop_test", "in_process": True})
    assert resp.status_code == 400  # the SystemExit sentinel → 400 (after capture)
    # only the authored role carries an assignment (the other roles have no JudgeConfig),
    # and it carries EXACTLY the persisted lens — the loop is byte-faithful. The persisted
    # JudgeConfig.assigned_flags is a tuple (app.py put_judge_endpoint), threaded as-stored.
    assert {r: list(v) for r, v in captured["assignments"].items()} == {"risk_judge": authored}
    assert set(captured["assignments"]) == {"risk_judge"}  # no other role is threaded


# ── A2a: the BYOK MODEL + the lens travel together, from one authored judge -> the grade ──


def test_authored_model_threads_from_put_judge_to_the_grade(bff_client, monkeypatch):
    """A2a — the BYOK leg of the loop. One audited ``PUT /v1/judges/risk_judge`` binds
    BOTH ``model="byo-claude"`` AND a chosen lens; ``POST /v1/run-eval`` threads BOTH
    ``models={'risk_judge': 'byo-claude'}`` and ``assignments={'risk_judge': <flags>}``
    into ``run_eval.run`` — so a judge authored on the user's BYO-Claude key grades with
    its authored lens. ``run_eval.run`` spied → $0. (The model-only thread is also covered
    by ``tests/test_byoc_provider.py::test_bff_threads_a_byo_claude_judge_model_into_the_run``;
    this asserts the model+lens co-travel from a SINGLE authored judge.)"""
    client, bff = bff_client
    authored = _lens_subset(bff, "risk_judge", n=1)

    put = client.put(
        "/v1/judges/risk_judge",
        json={"model": "byo-claude", "assigned_flags": authored, "validator_refs": []},
    )
    assert put.status_code == 200, put.text

    captured: dict = {}

    def spy_run(agent, **kwargs):
        captured["models"] = kwargs.get("models")
        captured["assignments"] = kwargs.get("assignments")
        raise SystemExit("stop after capturing the threaded model + lens")

    monkeypatch.setattr(bff.run_eval, "run", spy_run)
    resp = client.post("/v1/run-eval", json={"agent": "crud2_loop_test", "in_process": True})
    assert resp.status_code == 400  # the SystemExit sentinel → 400 (after capture)
    assert captured["models"] == {"risk_judge": "byo-claude"}
    # the lens co-travels (persisted as a tuple, threaded as-stored)
    assert {r: list(v) for r, v in captured["assignments"].items()} == {"risk_judge": authored}
